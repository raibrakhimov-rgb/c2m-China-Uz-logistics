import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
from datetime import datetime

# ============================================
# CONFIG
# ============================================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

START_ROW = 866  # январь 2026 начинается тут


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

    # удалить пустые
    df = df.dropna(how="all")

    # удалить unnamed колонки
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    # удалить первую безымянную колонку индекса
    df = df.reset_index(drop=True)

    # взять только январь 2026+
    df = df.iloc[START_ROW:].copy()

    # очистка колонок
    df.columns = df.columns.astype(str).str.strip()

    return df


df = load_data()


# ============================================
# FIND COLUMNS SAFE
# ============================================

def find_col(keywords):

    for col in df.columns:

        name = col.lower()

        for k in keywords:

            if k in name:
                return col

    return None


COL_PROJECT = find_col(["project", "проект"])
COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_SPLIT = find_col(["дроб"])
COL_REMARKS = find_col(["remark"])
COL_HUB_DAYS = find_col(["хаб"])


# ============================================
# TYPE CONVERT
# ============================================

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

# удалить строки без даты
df = df[df[COL_DATE].notna()]

# удалить строки до 2026
df = df[df[COL_DATE] >= "2026-01-01"]


# ============================================
# KPI CALC
# ============================================

total_weight = int(df[COL_WEIGHT].sum())
total_flights = df[COL_FLIGHT].nunique()
avg_weight = int(df[COL_WEIGHT].mean())

# transit time
if COL_ETD and COL_ATA:

    transit = (df[COL_ATA] - df[COL_ETD]).dt.days
    transit = transit[(transit > 0) & (transit < 60)]

    avg_transit = round(transit.mean(), 1)

else:
    avg_transit = 0


# ============================================
# HEADER
# ============================================

st.title("✈️ China → Uzbekistan Logistics Dashboard")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Weight", f"{total_weight:,} kg")
c2.metric("Flights", total_flights)
c3.metric("Avg Weight", f"{avg_weight} kg")
c4.metric("Transit Time", f"{avg_transit} days")


# ============================================
# FILTER PROJECT
# ============================================

projects = ["All"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.selectbox("Project", projects)

df_chart = df.copy()

if project != "All":
    df_chart = df_chart[df_chart[COL_PROJECT] == project]


# ============================================
# PERIOD SELECT
# ============================================

period = st.radio(
    "Period",
    ["Daily", "Weekly", "Monthly"],
    horizontal=True
)


# ============================================
# GROUP DATA
# ============================================

if period == "Daily":

    grouped = (
        df_chart.groupby(df_chart[COL_DATE].dt.date)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_DATE)
    )

    grouped.columns = ["date", "weight"]

elif period == "Weekly":

    grouped = (
        df_chart
        .groupby(df_chart[COL_DATE].dt.to_period("W"))
        [COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped["date"] = grouped[COL_DATE].astype(str)
    grouped["weight"] = grouped[COL_WEIGHT]

else:

    grouped = (
        df_chart
        .groupby(df_chart[COL_DATE].dt.to_period("M"))
        [COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped["date"] = grouped[COL_DATE].astype(str)
    grouped["weight"] = grouped[COL_WEIGHT]


# ============================================
# CHART
# ============================================

fig = px.bar(
    grouped,
    x="date",
    y="weight",
    title="Shipment Volume",
    text="weight"
)

fig.update_layout(

    height=500,

    xaxis=dict(
        tickangle=-45
    )
)

st.plotly_chart(fig, use_container_width=True)


# ============================================
# TABS
# ============================================

tab1, tab2 = st.tabs(["📋 Shipments", "📦 Split Shipments"])


# ============================================
# SHIPMENTS TABLE
# ============================================

with tab1:

    table = df.copy()

    # удалить batch no
    table = table.drop(columns=[find_col(["batch"])], errors="ignore")

    # удалить unnamed индекс
    table = table.reset_index(drop=True)

    # добавить номер
    table.insert(0, "№", table.index + 1)

    # формат дат
    for c in [COL_DATE, COL_ETD, COL_ATD, COL_ETA, COL_ATA]:

        if c in table.columns:
            table[c] = table[c].dt.strftime("%Y-%m-%d")

    st.dataframe(
        table,
        use_container_width=True,
        height=600
    )


# ============================================
# SPLIT SHIPMENTS
# ============================================

with tab2:

    if COL_SPLIT:

        split = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        split = split.reset_index(drop=True)

        split.insert(0, "№", split.index + 1)

        st.dataframe(split, use_container_width=True)

    else:

        st.info("No split shipments")
