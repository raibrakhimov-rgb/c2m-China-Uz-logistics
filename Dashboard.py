import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

# ============================================
# CONFIG
# ============================================

st.set_page_config(
    page_title="Логистика Китай → Узбекистан",
    layout="wide"
)

st.title("✈️ Сводная по вылетам Китай → Узбекистан")

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ============================================
# LOAD DATA
# ============================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    # удалить unnamed
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    # очистить названия
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.replace("\n", " ")
        .str.replace("  ", " ")
    )

    # данные с 2026
    df = df.iloc[866:].copy()

    df.reset_index(drop=True, inplace=True)

    return df


df = load_data()

# ============================================
# AUTO COLUMN DETECT
# ============================================

def find_column(possible_names):

    for name in df.columns:

        for p in possible_names:

            if p.lower() in name.lower():

                return name

    return None


COL_WEIGHT = find_column([
    "weight"
])

COL_CARTON = find_column([
    "carton"
])

COL_DATE = find_column([
    "Outbound date"
])

COL_PROJECT = find_column([
    "Проект"
])

COL_AWB = find_column([
    "AWB"
])

COL_ETD = find_column(["ETD"])
COL_ATA = find_column(["ATA"])

# ============================================
# TYPE CONVERT
# ============================================

if COL_WEIGHT:
    df[COL_WEIGHT] = pd.to_numeric(
        df[COL_WEIGHT],
        errors="coerce"
    )

if COL_DATE:
    df[COL_DATE] = pd.to_datetime(
        df[COL_DATE],
        errors="coerce"
    ).dt.date

if COL_ETD:
    df[COL_ETD] = pd.to_datetime(
        df[COL_ETD],
        errors="coerce"
    )

if COL_ATA:
    df[COL_ATA] = pd.to_datetime(
        df[COL_ATA],
        errors="coerce"
    )

# ============================================
# PROJECT FILTER
# ============================================

if COL_PROJECT:

    projects = ["Все"] + sorted(
        df[COL_PROJECT]
        .dropna()
        .astype(str)
        .unique()
    )

    selected = st.radio(
        "Проект:",
        projects,
        horizontal=True
    )

    if selected != "Все":

        df = df[
            df[COL_PROJECT].astype(str)
            == selected
        ]

# ============================================
# KPI
# ============================================

total_weight = int(
    df[COL_WEIGHT].sum()
) if COL_WEIGHT else 0

total_flights = (
    df[COL_AWB].nunique()
    if COL_AWB else 0
)

avg_weight = int(
    df[COL_WEIGHT].mean()
) if COL_WEIGHT else 0

transit = None

if COL_ETD and COL_ATA:

    temp = df.dropna(
        subset=[COL_ETD, COL_ATA]
    ).copy()

    temp["transit"] = (
        temp[COL_ATA]
        -
        temp[COL_ETD]
    ).dt.days

    temp = temp[
        (temp["transit"] >= 0)
        &
        (temp["transit"] <= 15)
    ]

    if len(temp) > 0:

        transit = round(
            temp["transit"].mean(),
            1
        )

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Общий вес",
    f"{total_weight:,} кг"
)

col2.metric(
    "Количество рейсов",
    total_flights
)

col3.metric(
    "Средний вес",
    f"{avg_weight} кг"
)

col4.metric(
    "Средний transit time",
    f"{transit} дней" if transit else "-"
)

# ============================================
# CHART
# ============================================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart = df.copy()

if period == "По дням":

    grouped = chart.groupby(
        COL_DATE
    )[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped[COL_DATE].astype(str)

elif period == "По неделям":

    chart["week"] = pd.to_datetime(
        chart[COL_DATE]
    ).dt.to_period("W").astype(str)

    grouped = chart.groupby(
        "week"
    )[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped["week"]

else:

    chart["month"] = pd.to_datetime(
        chart[COL_DATE]
    ).dt.to_period("M").astype(str)

    grouped = chart.groupby(
        "month"
    )[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped["month"]

fig = px.bar(

    grouped,

    x=COL_WEIGHT,

    y="label",

    orientation="h",

    text=COL_WEIGHT,

    height=700
)

fig.update_traces(
    textposition="inside",
    textangle=0
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ============================================
# TABLE
# ============================================

st.subheader("Список партий")

table = df.copy()

table.insert(
    0,
    "№",
    range(
        1,
        len(table)+1
    )
)

st.dataframe(
    table,
    use_container_width=True
)
