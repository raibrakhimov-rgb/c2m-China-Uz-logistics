import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# =====================================
# LOAD DATA
# =====================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.iloc[866:].reset_index(drop=True)

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    df.columns = df.columns.astype(str).str.strip()

    return df


df = load_data()

# =====================================
# FIND COLUMNS
# =====================================

def find_col(keys):

    for col in df.columns:
        name = col.lower()
        for k in keys:
            if k in name:
                return col
    return None


COL_PROJECT = find_col(["проект", "project"])
COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_SPLIT = find_col(["дроб"])
COL_ATA_SPLIT = find_col(["ata (при дроб"])
COL_ATA_EXT = find_col(["ata_ext"])
COL_HUB = find_col(["хаб"])
COL_TAS = find_col(["tas"])
COL_REMARKS = find_col(["remarks"])
COL_COMMENTS = find_col(["коммент"])

# =====================================
# CLEAN TYPES
# =====================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

for c in [COL_DATE, COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")

df = df.dropna(subset=[COL_DATE, COL_WEIGHT])

# =====================================
# TITLE
# =====================================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")

# =====================================
# FILTER
# =====================================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

# =====================================
# GROUP DATA
# =====================================

chart_df = df.copy()

if period == "По дням":

    grouped = chart_df.groupby(
        chart_df[COL_DATE].dt.date
    )[COL_WEIGHT].sum().reset_index()

    grouped["label"] = pd.to_datetime(grouped[COL_DATE]).dt.strftime("%Y-%m-%d")

elif period == "По неделям":

    grouped = chart_df.groupby(
        chart_df[COL_DATE].dt.to_period("W")
    )[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped[COL_DATE].astype(str)

else:

    grouped = chart_df.groupby(
        chart_df[COL_DATE].dt.to_period("M")
    )[COL_WEIGHT].sum().reset_index()

    grouped["label"] = grouped[COL_DATE].astype(str)

grouped = grouped.sort_values(COL_DATE)

# =====================================
# CHART (FIXED READABLE VERSION)
# =====================================

fig = px.bar(
    grouped,
    x="label",
    y=COL_WEIGHT,
    text=COL_WEIGHT,
)

fig.add_scatter(
    x=grouped["label"],
    y=grouped[COL_WEIGHT],
    mode="lines+markers",
    name="Trend"
)

fig.update_layout(
    height=500,
    xaxis_title="Дата",
    yaxis_title="Вес (кг)",
    xaxis_tickangle=-45,
    hovermode="x unified"
)

if len(grouped) > 30:
    fig.update_xaxes(range=[len(grouped)-30, len(grouped)])

st.plotly_chart(fig, use_container_width=True)

# =====================================
# TABS
# =====================================

tab1, tab2 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии"
])

# =====================================
# TABLE 1
# =====================================

with tab1:

    table = df.copy().reset_index(drop=True)

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", table.index + 1)

    if COL_DATE:
        table[COL_DATE] = table[COL_DATE].dt.date

    if COL_ETD:
        table[COL_ETD] = table[COL_ETD].dt.date

    if COL_ATD:
        table[COL_ATD] = table[COL_ATD].dt.date

    if COL_ETA:
        table[COL_ETA] = table[COL_ETA].dt.date

    if COL_ATA:
        table["ATA_time"] = table[COL_ATA].dt.strftime("%H:%M")
        table[COL_ATA] = table[COL_ATA].dt.date

    columns_order = [
        "№",
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
        "ATA_time",
        COL_HUB,
        COL_TAS,
        COL_REMARKS
    ]

    columns_order = [c for c in columns_order if c in table.columns]

    table = table[columns_order]

    st.dataframe(table, use_container_width=True)

# =====================================
# SPLIT TABLE
# =====================================

with tab2:

    if COL_SPLIT:

        split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split_df.groupby(COL_AWB):

            if len(g) < 2:
                continue

            cartons = g[COL_CARTON].dropna().astype(int).tolist()

            ata_split = None

            if COL_ATA_SPLIT in g.columns:
                ata_split = g[COL_ATA_SPLIT].dropna().astype(str).unique()

            rows.append({
                "AWB": awb,
                "Q-ty of flights": len(g),
                "Total cartons": sum(cartons),
                "Separate cartons": ", ".join(map(str, cartons)),
                "ATA (при дроблении)": ", ".join(ata_split) if ata_split is not None else ""
            })

        split_table = pd.DataFrame(rows)

        split_table.insert(0, "№", split_table.index + 1)

        st.dataframe(split_table, use_container_width=True)

    else:
        st.info("Нет дробленных партий")
