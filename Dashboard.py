import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
from datetime import datetime

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="Логистика Китай → Узбекистан",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"


# =========================
# LOAD DATA
# =========================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.dropna(how="all")

    df.columns = df.columns.astype(str).str.strip()

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    return df


df = load_data()


# =========================
# FIND COLUMN SAFE
# =========================

def find_column(possible):

    for col in df.columns:

        name = col.lower()

        for p in possible:
            if p in name:
                return col

    return None


COL_DATE = find_column(["outbound date", "дата"])
COL_WEIGHT = find_column(["weight", "вес"])
COL_PROJECT = find_column(["project", "проект"])
COL_AWB = find_column(["awb"])
COL_ETD = find_column(["etd"])
COL_ATA = find_column(["ata"])
COL_SPLIT = find_column(["дроб", "split"])


# =========================
# VALIDATE
# =========================

if COL_DATE is None or COL_WEIGHT is None:

    st.error("Не найдены критические колонки")
    st.write(df.columns.tolist())
    st.stop()


# =========================
# FORMAT
# =========================

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")
df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df = df.dropna(subset=[COL_DATE, COL_WEIGHT])


if COL_ATA:
    df[COL_ATA] = pd.to_datetime(df[COL_ATA], errors="coerce")

if COL_ETD:
    df[COL_ETD] = pd.to_datetime(df[COL_ETD], errors="coerce")


# =========================
# FILTER FROM 2026+
# =========================

df = df[df[COL_DATE] >= "2026-01-01"]


# =========================
# TRANSIT TIME SAFE
# =========================

if COL_ETD and COL_ATA:

    df["transit"] = (
        (df[COL_ATA] - df[COL_ETD])
        .dt.days
    )

    df.loc[df["transit"] < 0, "transit"] = None

else:
    df["transit"] = None


# =========================
# HEADER
# =========================

st.title("✈️ Логистика Китай → Узбекистан")


# =========================
# PROJECT FILTER
# =========================

projects = ["Все"]

if COL_PROJECT:
    projects += sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]


# =========================
# KPI
# =========================

total_weight = int(df[COL_WEIGHT].sum())
flights = df[COL_AWB].nunique() if COL_AWB else len(df)
avg_weight = int(df[COL_WEIGHT].mean())

if df["transit"].dropna().empty:
    avg_transit = 0
else:
    avg_transit = int(df["transit"].mean())


c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")
c2.metric("Количество рейсов", flights)
c3.metric("Средний вес", f"{avg_weight:,} кг")
c4.metric("Средний transit time", f"{avg_transit} дней")


# =========================
# PERIOD
# =========================

period = st.radio(
    "Период",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


chart = df.copy()


if period == "По дням":

    chart = (
        chart.groupby(COL_DATE)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_DATE)
    )


elif period == "По неделям":

    chart["week"] = chart[COL_DATE].dt.to_period("W").apply(lambda r: r.start_time)

    chart = (
        chart.groupby("week")[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values("week")
    )

    chart.rename(columns={"week": COL_DATE}, inplace=True)


else:

    chart["month"] = chart[COL_DATE].dt.to_period("M").apply(lambda r: r.start_time)

    chart = (
        chart.groupby("month")[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    chart.rename(columns={"month": COL_DATE}, inplace=True)


# =========================
# CHART
# =========================

fig = px.bar(
    chart,
    x=COL_DATE,
    y=COL_WEIGHT,
    text=COL_WEIGHT
)

fig.update_traces(
    textposition="inside",
    textangle=0
)

fig.update_layout(
    height=500
)

st.plotly_chart(fig, use_container_width=True)


# =========================
# TABS
# =========================

tab1, tab2 = st.tabs([
    "📦 Shipments",
    "📦 Split Shipments"
])


# =========================
# SHIPMENTS TABLE
# =========================

with tab1:

    search = st.text_input("Поиск")

    table = df.copy()

    if search:
        table = table.astype(str).apply(
            lambda row: row.str.contains(search, case=False).any(),
            axis=1
        )

        table = df[table]

    table = table.reset_index(drop=True)

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", table.index + 1)

    st.dataframe(
        table,
        use_container_width=True,
        height=600
    )


# =========================
# SPLIT TABLE
# =========================

with tab2:

    if COL_SPLIT:

        split = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        split = split.reset_index(drop=True)

        split.insert(0, "№", split.index + 1)

        st.dataframe(
            split,
            use_container_width=True,
            height=600
        )

    else:

        st.info("Нет split shipments")
