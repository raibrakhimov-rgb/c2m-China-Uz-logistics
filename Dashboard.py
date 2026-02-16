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

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ================= LOAD DATA =================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.iloc[866:].copy()

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


COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_AWB = find_col(["awb"])
COL_PROJECT = find_col(["project", "проект"])
COL_SPLIT = find_col(["дроб"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_COMMENT = find_col(["коммент"])
COL_DAYS_HUB = find_col(["хаб"])

required = [COL_WEIGHT, COL_CARTON, COL_DATE, COL_AWB]

if any(x is None for x in required):

    st.error("Не найдены обязательные колонки")
    st.write(df.columns.tolist())
    st.stop()

# ================= FORMAT =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce").dt.date

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

if COL_DAYS_HUB:
    df[COL_DAYS_HUB] = pd.to_numeric(df[COL_DAYS_HUB], errors="coerce").round()

df = df.dropna(subset=[COL_DATE])

# ================= HEADER =================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")

# ================= KPI =================

c1, c2, c3 = st.columns(3)

c1.metric("Рейсов", len(df))
c2.metric("Вес (кг)", f"{int(df[COL_WEIGHT].sum()):,}")
c3.metric("Коробов", f"{int(df[COL_CARTON].sum()):,}")

# ================= PROJECT FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]

# ================= GROUP =================

group = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

# ================= GROUP LOGIC =================

if group == "По дням":

    chart_df = chart_df.groupby(COL_DATE)[COL_WEIGHT].sum().reset_index()

    chart_df = chart_df.sort_values(COL_DATE)

    chart_df["label"] = chart_df[COL_DATE].astype(str)

elif group == "По неделям":

    chart_df["week"] = pd.to_datetime(chart_df[COL_DATE]).dt.to_period("W")

    grouped = chart_df.groupby("week")[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped["week"].astype(str)

    chart_df = grouped

else:

    chart_df["month"] = pd.to_datetime(chart_df[COL_DATE]).dt.to_period("M")

    grouped = chart_df.groupby("month")[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped["month"].astype(str)

    chart_df = grouped

# ================= PLOTLY CHART =================

fig = px.bar(
    chart_df,
    x="label",
    y=COL_WEIGHT,
    text=COL_WEIGHT
)

fig.update_layout(
    height=500,
    xaxis_title="",
    yaxis_title="Вес (кг)",
    xaxis_tickangle=-45
)

st.plotly_chart(fig, use_container_width=True)

# ================= TABS =================

tab1, tab2 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии"
])

# ================= TABLE =================

with tab1:

    table = df.copy()

    if COL_COMMENT:
        comments = table.pop(COL_COMMENT)
        table["Комментарии"] = comments

    table = table.reset_index(drop=True)

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", table.index + 1)

    st.dataframe(table, use_container_width=True)

# ================= SPLIT TABLE =================

with tab2:

    if COL_SPLIT:

        split = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split.groupby(COL_AWB):

            cartons = g[COL_CARTON].dropna().astype(int).tolist()

            if len(cartons) > 1:

                rows.append({
                    "AWB": awb,
                    "Q-ty of flights": len(cartons),
                    "Total No of cartons": sum(cartons),
                    "Q-ty of separate cartons": ", ".join(map(str, cartons))
                })

        if rows:

            split_table = pd.DataFrame(rows)

            split_table.insert(0, "№", split_table.index + 1)

            st.dataframe(split_table, use_container_width=True)

        else:
            st.info("Дробленных партий нет")

    else:
        st.info("Нет колонки 'Дробление'")
