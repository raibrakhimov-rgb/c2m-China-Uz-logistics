import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Свод по рейсам Китай-Узбекистан",
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
# COLUMN FINDER
# =====================================================

def find_col(names, columns):

    for col in columns:

        c = col.lower()

        for name in names:

            if name in c:
                return col

    return None


COL_PROJECT = find_col(["проект"], df.columns)
COL_WEIGHT = find_col(["weight"], df.columns)
COL_DATE = find_col(["outbound date"], df.columns)
COL_AWB = find_col(["awb"], df.columns)
COL_FLIGHT = find_col(["flight"], df.columns)
COL_VIA = find_col(["via"], df.columns)
COL_ATD = find_col(["atd"], df.columns)
COL_ATA = find_col(["ata"], df.columns)
COL_SPLIT = find_col(["дроб"], df.columns)


# =====================================================
# CLEAN DATA
# =====================================================

DATE_COLUMNS = []

for col in df.columns:

    if any(x in col.lower() for x in ["date", "etd", "atd", "eta", "ata", "хаб"]):

        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

        DATE_COLUMNS.append(col)


df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df["Transit"] = (df[COL_ATA] - df[COL_ATD]).dt.days

df = df.dropna(subset=[COL_DATE])


# =====================================================
# REMOVE UNUSED COLUMNS
# =====================================================

REMOVE = ["pod", "ata_ext", "ata.1", "комментар"]

drop_cols = []

for col in df.columns:

    if any(x in col.lower() for x in REMOVE):

        drop_cols.append(col)

df = df.drop(columns=drop_cols, errors="ignore")


# =====================================================
# HELPERS
# =====================================================

def safe_index(data):

    if "№" in data.columns:
        data = data.drop(columns=["№"])

    data.insert(0, "№", range(1, len(data)+1))

    return data


def format_dates(data):

    for col in DATE_COLUMNS:

        if col in data.columns:

            data[col] = pd.to_datetime(data[col], errors="coerce").dt.strftime("%d-%m-%Y")

    return data


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.header("Фильтры")

projects = st.sidebar.multiselect(
    "Проект",
    sorted(df[COL_PROJECT].dropna().unique()),
    default=sorted(df[COL_PROJECT].dropna().unique())
)

vias = st.sidebar.multiselect(
    "Транзитный город",
    sorted(df[COL_VIA].dropna().unique()),
    default=sorted(df[COL_VIA].dropna().unique())
)

date_range = st.sidebar.date_input(
    "Период",
    [df[COL_DATE].min(), df[COL_DATE].max()]
)


# =====================================================
# FILTER DATA
# =====================================================

filtered = df.copy()

filtered = filtered[
    filtered[COL_PROJECT].isin(projects)
]

filtered = filtered[
    filtered[COL_VIA].isin(vias)
]

filtered = filtered[
    (filtered[COL_DATE] >= pd.to_datetime(date_range[0])) &
    (filtered[COL_DATE] <= pd.to_datetime(date_range[1]))
]


# =====================================================
# HEADER
# =====================================================

st.title("Свод по рейсам Китай-Узбекистан")


# =====================================================
# KPI
# =====================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{int(filtered[COL_WEIGHT].sum()):,} кг")

c2.metric("Количество партий", len(filtered))

c3.metric("Средний вес", f"{int(filtered[COL_WEIGHT].mean()):,} кг")

c4.metric(
    "Среднее транзитное время",
    f"{int(filtered['Transit'].mean()) if filtered['Transit'].notna().sum() else 0} дней"
)


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

trend["Дата"] = trend["Дата"].dt.strftime("%d-%m-%Y")

fig = px.bar(trend, x="Дата", y="Вес", text="Вес")

fig.update_traces(textposition="outside")

st.plotly_chart(fig, use_container_width=True)


# =====================================================
# BREAKDOWN
# =====================================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("Объём по проектам")

    proj = (
        filtered.groupby(COL_PROJECT)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    st.plotly_chart(px.bar(proj, x=COL_PROJECT, y=COL_WEIGHT, text=COL_WEIGHT), use_container_width=True)


with col2:

    st.subheader("Объём по транзитным городам Китая")

    via = (
        filtered.groupby(COL_VIA)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    st.plotly_chart(px.pie(via, names=COL_VIA, values=COL_WEIGHT), use_container_width=True)


# =====================================================
# TABS
# =====================================================

tab1, tab2 = st.tabs(["Список партий", "Дробленные партии"])


# =====================================================
# TAB 1 LIST
# =====================================================

with tab1:

    search = st.text_input("Поиск по AWB")

    table = filtered.copy()

    if search:

        table = table[
            table[COL_AWB].astype(str)
            .str.contains(search, case=False, na=False)
        ]

    table = table.sort_values(COL_DATE)

    table = format_dates(table)

    table = safe_index(table)

    st.dataframe(table, use_container_width=True, height=600)


# =====================================================
# TAB 2 SPLIT
# =====================================================

with tab2:

    if COL_SPLIT:

        split = filtered[
            filtered[COL_SPLIT].astype(str)
            .str.contains("да", case=False, na=False)
        ].copy()

        split = split.sort_values(COL_DATE)

        split = format_dates(split)

        split = safe_index(split)

        st.dataframe(split, use_container_width=True, height=600)

    else:

        st.info("Нет дробленных партий")
