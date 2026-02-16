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

    df = df.dropna(how="all")

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    df.columns = df.columns.astype(str).str.strip()

    # только данные с 867 строки (2026 год)
    df = df.iloc[866:].reset_index(drop=True)

    return df


df = load_data()


# ================= FIND COLUMNS =================

def find_col(keys):

    for col in df.columns:

        name = col.lower()

        for k in keys:

            if k in name:
                return col

    return None


COL_WEIGHT = find_col(["weight", "kg"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date", "date"])
COL_AWB = find_col(["awb"])
COL_PROJECT = find_col(["проект", "project"])
COL_SPLIT = find_col(["дроб"])


REQUIRED = [
    COL_WEIGHT,
    COL_CARTON,
    COL_DATE,
    COL_AWB,
    COL_PROJECT
]


if any(x is None for x in REQUIRED):

    st.error("❌ Не найдены обязательные колонки")

    st.write(df.columns.tolist())

    st.stop()


# ================= CLEAN DATA =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")
df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

df = df.dropna(subset=[COL_DATE, COL_WEIGHT])


# ================= HEADER =================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")


# ================= KPI =================

total_flights = df[COL_AWB].nunique()

total_weight = int(df[COL_WEIGHT].sum())

total_cartons = int(df[COL_CARTON].sum())

col1, col2, col3 = st.columns(3)

col1.metric("Количество рейсов", total_flights)

col2.metric("Общий вес (кг)", f"{total_weight:,}".replace(",", " "))

col3.metric("Количество коробов", f"{total_cartons:,}".replace(",", " "))


# ================= PROJECT FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if project != "Все":

    df = df[df[COL_PROJECT] == project]


# ================= GROUP FILTER =================

group = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


# ================= GROUP DATA =================

chart_df = df.copy()

months = {
    1:"январь",2:"февраль",3:"март",
    4:"апрель",5:"май",6:"июнь",
    7:"июль",8:"август",9:"сентябрь",
    10:"октябрь",11:"ноябрь",12:"декабрь"
}


if group == "По дням":

    chart_df["label"] = chart_df[COL_DATE].dt.strftime("%d.%m")

    chart_df["sort"] = chart_df[COL_DATE]


elif group == "По неделям":

    chart_df["start"] = chart_df[COL_DATE] - pd.to_timedelta(chart_df[COL_DATE].dt.weekday, unit="D")

    chart_df["label"] = chart_df["start"].dt.strftime("%d.%m") + "-" + (chart_df["start"]+pd.Timedelta(days=6)).dt.strftime("%d.%m")

    chart_df["sort"] = chart_df["start"]


else:

    chart_df["label"] = chart_df[COL_DATE].dt.month.map(months) + " " + chart_df[COL_DATE].dt.year.astype(str)

    chart_df["sort"] = chart_df[COL_DATE].dt.to_period("M").dt.to_timestamp()


grouped = chart_df.groupby(["label","sort"])[COL_WEIGHT].sum().reset_index()

grouped = grouped.sort_values("sort")


# ================= INTERACTIVE CHART =================

fig = px.bar(
    grouped,
    x="label",
    y=COL_WEIGHT,
    text=COL_WEIGHT,
)

fig.update_traces(
    hovertemplate="Период: %{x}<br>Вес: %{y} кг"
)

fig.update_layout(
    xaxis_title="",
    yaxis_title="Вес (кг)",
    height=450
)

st.plotly_chart(fig, use_container_width=True)


# ================= TABS =================

tab1, tab2 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии"
])


# ================= LIST =================

with tab1:

    table = df.copy()

    remove_cols = [
        "Batch No",
        "Дней до прибытия из SWE до Терминала TAS",
        "Дней до прибытия из SWE до ХАБа",
        "Поступления на склад",
        "wh_ext",
        "Поступления на склад ХАБ",
        "POD",
        "Remarks"
    ]

    for col in remove_cols:

        if col in table.columns:
            table = table.drop(columns=[col])

    table = table.sort_values(COL_DATE, ascending=False)

    table = table.reset_index(drop=True)

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", range(1, len(table)+1))

    st.dataframe(table, use_container_width=True)


# ================= SPLIT =================

with tab2:

    if not COL_SPLIT:

        st.info("Нет колонки дробления")

    else:

        split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split_df.groupby(COL_AWB):

            if len(g) < 2:
                continue

            cartons = g[COL_CARTON].dropna().astype(int).tolist()

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

            split_table.insert(0, "№", range(1, len(split_table)+1))

            st.dataframe(split_table, use_container_width=True)

        else:

            st.info("Нет дробленных партий")
