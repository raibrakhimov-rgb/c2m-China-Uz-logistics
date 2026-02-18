import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Executive Dashboard | Свод по рейсам Китай-Узбекистан",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

START_ROW = 874


# =====================================================
# LOAD DATA
# =====================================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(BytesIO(r.content))

    df.columns = df.columns.astype(str).str.strip()

    df = df.iloc[START_ROW:].reset_index(drop=True)

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    return df


df = load_data()


# =====================================================
# FIND COLUMNS
# =====================================================

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


# =====================================================
# CLEAN DATA
# =====================================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce", dayfirst=True)

df[COL_ATD] = pd.to_datetime(df[COL_ATD], errors="coerce", dayfirst=True)

df[COL_ATA] = pd.to_datetime(df[COL_ATA], errors="coerce", dayfirst=True)


# TRANSIT TIME
df["Transit"] = (df[COL_ATA] - df[COL_ATD]).dt.days

df = df.dropna(subset=[COL_DATE])


# =====================================================
# SAFE INDEX FUNCTION
# =====================================================

def safe_index(df):

    if "№" in df.columns:

        df = df.drop(columns=["№"])

    df.insert(0, "№", range(1, len(df) + 1))

    return df


# =====================================================
# SIDEBAR FILTERS
# =====================================================

st.sidebar.header("Фильтры")

projects = st.sidebar.multiselect(
    "Проект",
    sorted(df[COL_PROJECT].dropna().unique()),
    default=sorted(df[COL_PROJECT].dropna().unique())
)

vias = st.sidebar.multiselect(
    "VIA",
    sorted(df[COL_VIA].dropna().unique()),
    default=sorted(df[COL_VIA].dropna().unique())
)

date_range = st.sidebar.date_input(
    "Период",
    [
        df[COL_DATE].min(),
        df[COL_DATE].max()
    ]
)


# =====================================================
# APPLY FILTERS
# =====================================================

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


# =====================================================
# HEADER
# =====================================================

st.title("Свод по рейсам Китай-Узбекистан")


# =====================================================
# KPI BLOCK
# =====================================================

total_weight = int(filtered[COL_WEIGHT].sum())

total_shipments = len(filtered)

avg_weight = int(filtered[COL_WEIGHT].mean()) if total_shipments else 0

avg_transit = int(filtered["Transit"].mean()) if filtered["Transit"].notna().sum() else 0


c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")

c2.metric("Количество партий", total_shipments)

c3.metric("Средний вес", f"{avg_weight} кг")

c4.metric("Среднее транзитное время", f"{avg_transit} дней")


# =====================================================
# TREND CHART
# =====================================================

st.subheader("Перевезенные партии, кг")

trend = (
    filtered
    .sort_values(COL_DATE)
    .groupby(filtered[COL_DATE].dt.date)[COL_WEIGHT]
    .sum()
    .reset_index()
)

trend.columns = ["Дата", "Вес"]

trend["Дата"] = pd.to_datetime(trend["Дата"])

trend = trend.sort_values("Дата")

trend["Дата_str"] = trend["Дата"].dt.strftime("%d-%m-%Y")


fig = px.bar(

    trend,

    x="Дата_str",

    y="Вес",

    text="Вес"
)

fig.update_traces(

    textposition="outside",

    textangle=0
)

fig.update_layout(

    height=500,

    xaxis_title="Дата",

    yaxis_title="Вес"
)

st.plotly_chart(

    fig,

    use_container_width=True
)


# =====================================================
# CUMULATIVE CHART
# =====================================================

st.subheader("Накопительный объем")

trend["Cumulative"] = trend["Вес"].cumsum()

fig2 = px.line(

    trend,

    x="Дата_str",

    y="Cumulative"
)

st.plotly_chart(

    fig2,

    use_container_width=True
)


# =====================================================
# PROJECT BREAKDOWN
# =====================================================

col1, col2 = st.columns(2)


with col1:

    st.subheader("Объем по проектам")

    proj = (
        filtered
        .groupby(COL_PROJECT)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_WEIGHT, ascending=False)
    )

    fig_proj = px.bar(

        proj,

        x=COL_PROJECT,

        y=COL_WEIGHT,

        text=COL_WEIGHT
    )

    st.plotly_chart(

        fig_proj,

        use_container_width=True
    )


with col2:

    st.subheader("Объем по VIA")

    via = (
        filtered
        .groupby(COL_VIA)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    fig_via = px.pie(

        via,

        names=COL_VIA,

        values=COL_WEIGHT
    )

    st.plotly_chart(

        fig_via,

        use_container_width=True
    )


# =====================================================
# SEARCH TABLE
# =====================================================

st.subheader("Поиск партии")

awb_search = st.text_input("Введите AWB номер")


table = filtered.copy()


if awb_search:

    table = table[
        table[COL_AWB]
        .astype(str)
        .str.contains(awb_search, case=False, na=False)
    ]


table = table.sort_values(COL_DATE)

table[COL_DATE] = table[COL_DATE].dt.strftime("%d-%m-%Y")

table = safe_index(table)


st.dataframe(

    table,

    use_container_width=True,

    height=600
)
