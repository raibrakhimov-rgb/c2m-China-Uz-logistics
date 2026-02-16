import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
from datetime import datetime

# ================= CONFIG =================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    # DATA STARTS FROM 2026
    df = df.iloc[866:].reset_index(drop=True)

    # CLEAN COLUMN NAMES
    df.columns = df.columns.astype(str).str.strip()

    # REMOVE UNNAMED COLUMNS
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    return df


df = load_data()

# ================= FIND COLUMN =================

def find_col(names):

    for col in df.columns:

        for name in names:

            if name.lower() in col.lower():
                return col

    return None


COL_PROJECT = find_col(["проект", "project"])
COL_DATE = find_col(["outbound date"])
COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_REMARKS = find_col(["remark"])
COL_SPLIT = find_col(["дроб"])


# ================= DATE CLEAN =================

for c in [COL_DATE, COL_ETD, COL_ETA, COL_ATD, COL_ATA]:

    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")

# KEEP ONLY 2026+
df = df[df[COL_DATE] >= "2026-01-01"]

# ================= FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

selected_project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

filtered = df.copy()

if selected_project != "Все":

    filtered = filtered[filtered[COL_PROJECT] == selected_project]

# ================= KPI =================

st.markdown("## KPI")

col1, col2, col3, col4 = st.columns(4)

total_weight = filtered[COL_WEIGHT].sum()
total_flights = filtered[COL_AWB].nunique()
avg_weight = filtered[COL_WEIGHT].mean()

# CORRECT TRANSIT TIME
transit_days = None

if COL_ETD and COL_ATA:

    valid = filtered.dropna(subset=[COL_ETD, COL_ATA])

    valid["transit"] = (valid[COL_ATA] - valid[COL_ETD]).dt.days

    valid = valid[(valid["transit"] >= 0) & (valid["transit"] <= 15)]

    if len(valid) > 0:
        transit_days = valid["transit"].mean()

col1.metric("Общий вес", f"{total_weight:,.0f} кг")
col2.metric("Рейсов", total_flights)
col3.metric("Средний вес", f"{avg_weight:,.0f} кг")

if transit_days:
    col4.metric("Transit time", f"{transit_days:.1f} дней")
else:
    col4.metric("Transit time", "-")

# ================= CHART =================

st.markdown("## Объёмы")

period = st.radio(
    "",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart = filtered.copy()

if period == "По дням":

    chart = chart.groupby(COL_DATE)[COL_WEIGHT].sum().reset_index()

    chart = chart.sort_values(COL_DATE)

    chart = chart.tail(30)

    fig = px.bar(
        chart,
        x=COL_DATE,
        y=COL_WEIGHT,
        text=COL_WEIGHT
    )

elif period == "По неделям":

    chart["week"] = chart[COL_DATE].dt.to_period("W").astype(str)

    chart = chart.groupby("week")[COL_WEIGHT].sum().reset_index()

    fig = px.bar(chart, x="week", y=COL_WEIGHT, text=COL_WEIGHT)

else:

    chart["month"] = chart[COL_DATE].dt.to_period("M").astype(str)

    chart = chart.groupby("month")[COL_WEIGHT].sum().reset_index()

    fig = px.bar(chart, x="month", y=COL_WEIGHT, text=COL_WEIGHT)

fig.update_layout(height=400)

st.plotly_chart(fig, use_container_width=True)

# ================= TABLE =================

st.markdown("## Список партий")

table = filtered.copy()

# REMOVE UNWANTED COLUMNS

drop_cols = []

for col in table.columns:

    if col.lower().startswith("batch"):
        drop_cols.append(col)

table = table.drop(columns=drop_cols, errors="ignore")

# FORMAT DATE WITHOUT TIME

for c in [COL_DATE, COL_ETD, COL_ETA, COL_ATD, COL_ATA]:

    if c:
        table[c] = table[c].dt.date

# STRICT COLUMN ORDER

ordered = [

    COL_PROJECT,
    COL_CARTON,
    COL_WEIGHT,
    COL_DATE,
    COL_AWB,
    COL_FLIGHT,
    COL_VIA,
    COL_ETD,
    COL_ATD,
    COL_ETA,
    COL_ATA,
    COL_REMARKS

]

ordered = [c for c in ordered if c in table.columns]

table = table[ordered]

# ADD №

table.insert(0, "№", range(1, len(table) + 1))

# SEARCH

search = st.text_input("Поиск")

if search:

    mask = table.astype(str).apply(
        lambda row: row.str.contains(search, case=False).any(),
        axis=1
    )

    table = table[mask]

st.dataframe(
    table,
    use_container_width=True,
    height=600
)

# ================= SPLIT =================

st.markdown("## Дробленные партии")

if COL_SPLIT:

    split = filtered[
        filtered[COL_SPLIT].astype(str).str.lower() == "да"
    ]

    rows = []

    for awb, g in split.groupby(COL_AWB):

        rows.append({

            "AWB": awb,
            "Flights": len(g),
            "Cartons": g[COL_CARTON].sum(),
            "ATA (при дроблении)": g[COL_ATA].max()

        })

    split_table = pd.DataFrame(rows)

    split_table.insert(0, "№", range(1, len(split_table)+1))

    st.dataframe(split_table, use_container_width=True)

else:

    st.info("Нет дробленных партий")
