import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

# ================= CONFIG =================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

XLSX_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

MONTHS_RU = {
    1:"январь",2:"февраль",3:"март",4:"апрель",5:"май",6:"июнь",
    7:"июль",8:"август",9:"сентябрь",10:"октябрь",11:"ноябрь",12:"декабрь"
}

# ================= LOAD DATA =================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(XLSX_URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.iloc[866:].reset_index(drop=True)

    df = df.dropna(how="all")

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    df.columns = df.columns.astype(str).str.strip()

    return df


df = load_data()

# ================= FIND COL =================

def find_col(keys):

    for col in df.columns:
        name = col.lower()
        for k in keys:
            if k in name:
                return col
    return None


COL_WEIGHT = find_col(["weight", "kg"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_PROJECT = find_col(["project", "проект"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_SPLIT = find_col(["дроб"])
COL_VIA = find_col(["via"])

# ================= CLEAN TYPES =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")
df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

df = df.dropna(subset=[COL_DATE, COL_WEIGHT])

# ================= HEADER =================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")

# ================= SUMMARY =================

c1, c2, c3 = st.columns(3)

c1.metric("Количество рейсов", len(df))
c2.metric("Общий вес (кг)", f"{int(df[COL_WEIGHT].sum()):,}".replace(",", " "))
c3.metric("Средний вес рейса (кг)", f"{int(df[COL_WEIGHT].mean()):,}".replace(",", " "))

# ================= PROJECT FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio("Проект:", projects, horizontal=True)

if project != "Все":
    df = df[df[COL_PROJECT] == project]

# ================= PERIOD =================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

# ================= GROUP =================

if period == "По дням":

    chart_df["label"] = chart_df[COL_DATE].dt.strftime("%d.%m")
    grouped = chart_df.groupby([COL_DATE, "label"])[COL_WEIGHT].sum().reset_index()
    grouped = grouped.sort_values(COL_DATE)

elif period == "По неделям":

    chart_df["start"] = chart_df[COL_DATE] - pd.to_timedelta(chart_df[COL_DATE].dt.weekday, unit="D")

    chart_df["label"] = (
        chart_df["start"].dt.strftime("%d.%m")
        + "-"
        + (chart_df["start"] + pd.Timedelta(days=6)).dt.strftime("%d.%m")
    )

    grouped = chart_df.groupby(["start", "label"])[COL_WEIGHT].sum().reset_index()
    grouped = grouped.sort_values("start")

else:

    chart_df["month"] = chart_df[COL_DATE].dt.month
    chart_df["year"] = chart_df[COL_DATE].dt.year

    chart_df["label"] = chart_df["month"].map(MONTHS_RU) + " " + chart_df["year"].astype(str)

    grouped = chart_df.groupby(["year", "month", "label"])[COL_WEIGHT].sum().reset_index()
    grouped = grouped.sort_values(["year", "month"])

# ================= CHART =================

fig = px.bar(
    grouped,
    x="label",
    y=COL_WEIGHT,
    text=COL_WEIGHT,
    hover_data={COL_WEIGHT:":,.0f"},
)

fig.update_layout(
    height=500,
    xaxis_title="",
    yaxis_title="Вес (кг)",
)

fig.update_traces(
    textposition="outside"
)

st.plotly_chart(fig, use_container_width=True)

# ================= TABS =================

tab1, tab2 = st.tabs(["📋 Список партий", "📦 Дробленные партии"])

# ================= LIST =================

with tab1:

    table = df.copy()

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", range(1, len(table)+1))

    remove_cols = [
        "Batch No",
        "ATA.1",
        "Remarks",
        "POD",
        "wh_ext",
        "Поступления на склад",
        "Поступления на склад ХАБ"
    ]

    table = table.drop(columns=[c for c in remove_cols if c in table.columns], errors="ignore")

    if COL_VIA and COL_FLIGHT:
        cols = list(table.columns)
        cols.insert(cols.index(COL_FLIGHT)+1, cols.pop(cols.index(COL_VIA)))
        table = table[cols]

    st.dataframe(table, use_container_width=True, hide_index=True)

# ================= SPLIT =================

with tab2:

    if COL_SPLIT:

        split_df = df[df[COL_SPLIT].astype(str).str.lower()=="да"]

        rows = []

        for awb, g in split_df.groupby(COL_AWB):

            if len(g)<2:
                continue

            cartons = g[COL_CARTON].astype(int).tolist()

            rows.append({
                "AWB": awb,
                "Q-ty of flights": len(g),
                "Total No of cartons": sum(cartons),
                "Q-ty of separate cartons": ", ".join(map(str, cartons))
            })

        if rows:

            split_table = pd.DataFrame(rows)

            if "№" in split_table.columns:
                split_table = split_table.drop(columns=["№"])

            split_table.insert(0,"№",range(1,len(split_table)+1))

            st.dataframe(split_table, use_container_width=True, hide_index=True)

        else:

            st.info("Нет дробленных партий")
