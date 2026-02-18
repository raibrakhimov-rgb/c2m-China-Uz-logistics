import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# ============================================
# CONFIG
# ============================================

st.set_page_config(
    page_title="Executive Dashboard | Китай → Узбекистан",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

START_ROW = 874


# ============================================
# LOAD DATA
# ============================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(BytesIO(r.content))

    df.columns = df.columns.astype(str).str.strip()

    df = df.iloc[START_ROW:].reset_index(drop=True)

    return df


df = load_data()


# ============================================
# COLUMN FINDER
# ============================================

def find_col(names):

    for col in df.columns:

        c = col.lower()

        for name in names:

            if name in c:
                return col

    return None


COL_PROJECT = find_col(["проект"])
COL_WEIGHT = find_col(["weight"])
COL_DATE = find_col(["outbound date"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata.1"])


# ============================================
# CLEAN TYPES
# ============================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

df[COL_ATD] = pd.to_datetime(df[COL_ATD], errors="coerce")

df[COL_ATA] = pd.to_datetime(df[COL_ATA], errors="coerce")


df["Transit"] = (df[COL_ATA] - df[COL_ATD]).dt.days

df = df.dropna(subset=[COL_DATE])


# ============================================
# SIDEBAR FILTERS (Power BI style)
# ============================================

st.sidebar.header("Фильтры")

projects = st.sidebar.multiselect(
    "Проект",
    df[COL_PROJECT].dropna().unique(),
    default=df[COL_PROJECT].dropna().unique()
)

vias = st.sidebar.multiselect(
    "VIA",
    df[COL_VIA].dropna().unique(),
    default=df[COL_VIA].dropna().unique()
)

date_range = st.sidebar.date_input(
    "Период",
    [
        df[COL_DATE].min(),
        df[COL_DATE].max()
    ]
)


# ============================================
# APPLY FILTERS
# ============================================

filtered = df.copy()

filtered = filtered[
    filtered[COL_PROJECT].isin(projects)
]

filtered = filtered[
    filtered[COL_VIA].isin(vias)
]

filtered = filtered[
    (filtered[COL_DATE] >= pd.to_datetime(date_range[0]))
    &
    (filtered[COL_DATE] <= pd.to_datetime(date_range[1]))
]


# ============================================
# EXECUTIVE KPIs
# ============================================

total_weight = int(filtered[COL_WEIGHT].sum())

total_shipments = len(filtered)

avg_weight = int(filtered[COL_WEIGHT].mean())

avg_transit = int(filtered["Transit"].mean())

col1, col2, col3, col4 = st.columns(4)

col1.metric("Общий вес", f"{total_weight:,} кг")

col2.metric("Количество партий", total_shipments)

col3.metric("Средний вес", f"{avg_weight} кг")

col4.metric("Средний transit time", f"{avg_transit} дней")


# ============================================
# TREND CHART
# ============================================

st.subheader("Тренд перевозок")

trend = (
    filtered
    .sort_values(COL_DATE)
    .groupby(filtered[COL_DATE].dt.date)[COL_WEIGHT]
    .sum()
    .reset_index()
)

trend.columns = ["Дата", "Вес"]

trend["Дата"] = pd.to_datetime(trend["Дата"])

fig = px.bar(
    trend,
    x="Дата",
    y="Вес",
    text="Вес"
)

fig.update_traces(textposition="outside")

st.plotly_chart(fig, use_container_width=True)


# ============================================
# CUMULATIVE CHART
# ============================================

st.subheader("Накопительный объем")

trend["Cumulative"] = trend["Вес"].cumsum()

fig2 = px.line(
    trend,
    x="Дата",
    y="Cumulative"
)

st.plotly_chart(fig2, use_container_width=True)


# ============================================
# PROJECT BREAKDOWN
# ============================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("По проектам")

    proj = (
        filtered
        .groupby(COL_PROJECT)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_WEIGHT, ascending=False)
    )

    fig = px.bar(
        proj,
        x=COL_PROJECT,
        y=COL_WEIGHT,
        text=COL_WEIGHT
    )

    st.plotly_chart(fig, use_container_width=True)


with col2:

    st.subheader("По VIA")

    via = (
        filtered
        .groupby(COL_VIA)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    fig = px.pie(
        via,
        names=COL_VIA,
        values=COL_WEIGHT
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================
# FLIGHT ANALYSIS
# ============================================

st.subheader("По рейсам")

flight = (
    filtered
    .groupby(COL_FLIGHT)[COL_WEIGHT]
    .sum()
    .reset_index()
    .sort_values(COL_WEIGHT, ascending=False)
)

fig = px.bar(
    flight,
    x=COL_FLIGHT,
    y=COL_WEIGHT
)

st.plotly_chart(fig, use_container_width=True)


# ============================================
# SEARCH AWB
# ============================================

st.subheader("Поиск партии")

awb_search = st.text_input("Введите AWB")

table = filtered.copy()

if awb_search:

    table = table[
        table[COL_AWB].astype(str)
        .str.contains(awb_search)
    ]


table = table.sort_values(COL_DATE)

table[COL_DATE] = table[COL_DATE].dt.strftime("%d-%m-%Y")

table.insert(0, "№", range(1, len(table)+1))

st.dataframe(table, use_container_width=True)
