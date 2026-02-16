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

# ================= STYLE =================

st.markdown("""
<style>

.main {
    background-color:#f7f9fc;
}

.metric-card {
    background:white;
    padding:15px;
    border-radius:10px;
    box-shadow:0 1px 5px rgba(0,0,0,0.1);
}

</style>
""", unsafe_allow_html=True)

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

    df = df.iloc[866:].reset_index(drop=True)

    df.columns = df.columns.astype(str).str.strip()

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    return df


df = load_data()

# ================= FIND COLUMN =================

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
COL_PROJECT = find_col(["проект", "project"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_SPLIT = find_col(["дроб"])


if COL_PROJECT is None:

    st.error("Колонка 'Проект' не найдена")
    st.write(df.columns.tolist())
    st.stop()

# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")
df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:

    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")

df = df.dropna(subset=[COL_DATE])

# ================= HEADER =================

st.title("✈️ China → Uzbekistan Logistics Dashboard")

# ================= FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

filtered = df.copy()

if project != "Все":

    filtered = filtered[filtered[COL_PROJECT] == project]

# ================= KPI =================

col1, col2, col3, col4 = st.columns(4)

total_weight = filtered[COL_WEIGHT].sum()
total_flights = filtered[COL_AWB].nunique()
avg_weight = filtered[COL_WEIGHT].mean()

transit = None

if COL_ETD and COL_ATA:

    transit = (filtered[COL_ATA] - filtered[COL_ETD]).dt.days.mean()

col1.metric("Общий вес", f"{total_weight:,.0f} кг")
col2.metric("Количество рейсов", total_flights)
col3.metric("Средний вес", f"{avg_weight:,.0f} кг")

if transit:
    col4.metric("Средний transit time", f"{transit:.1f} дней")
else:
    col4.metric("Средний transit time", "—")

# ================= PERIOD SELECT =================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = filtered.copy()

# ================= DAILY =================

if period == "По дням":

    chart_df = chart_df.sort_values(COL_DATE)

    last30 = chart_df.tail(30)

    daily = last30.groupby(COL_DATE)[COL_WEIGHT].sum().reset_index()

    fig = px.bar(
        daily,
        x=COL_DATE,
        y=COL_WEIGHT,
        text=COL_WEIGHT
    )

    fig.update_layout(height=400)

    st.plotly_chart(fig, use_container_width=True)

# ================= WEEKLY =================

elif period == "По неделям":

    chart_df["week"] = chart_df[COL_DATE].dt.to_period("W").astype(str)

    weekly = chart_df.groupby("week")[COL_WEIGHT].sum().reset_index()

    fig = px.bar(
        weekly,
        x="week",
        y=COL_WEIGHT,
        text=COL_WEIGHT
    )

    st.plotly_chart(fig, use_container_width=True)

# ================= MONTHLY =================

else:

    chart_df["month"] = chart_df[COL_DATE].dt.to_period("M").astype(str)

    monthly = chart_df.groupby("month")[COL_WEIGHT].sum().reset_index()

    fig = px.bar(
        monthly,
        x="month",
        y=COL_WEIGHT,
        text=COL_WEIGHT
    )

    st.plotly_chart(fig, use_container_width=True)

# ================= TABS =================

tab1, tab2 = st.tabs(["📋 Список партий", "📦 Дробленные партии"])

# ================= LIST =================

with tab1:

    table = filtered.copy()

    table = table.sort_values(COL_DATE, ascending=False)

    table = table.reset_index(drop=True)

    if "№" in table.columns:
        table.drop(columns=["№"], inplace=True)

    table.insert(0, "№", table.index + 1)

    st.dataframe(
        table,
        use_container_width=True,
        height=600
    )

# ================= SPLIT =================

with tab2:

    if COL_SPLIT is None:

        st.info("Нет колонки дробления")

    else:

        split = filtered[filtered[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split.groupby(COL_AWB):

            cartons = g[COL_CARTON].tolist()

            ata_split = None

            if COL_ATA:
                ata_split = g[COL_ATA].max()

            rows.append({

                "AWB": awb,
                "Flights": len(g),
                "Total cartons": sum(cartons),
                "Parts": ", ".join(map(str, cartons)),
                "ATA (при дроблении)": ata_split

            })

        split_table = pd.DataFrame(rows)

        split_table.insert(0, "№", split_table.index + 1)

        st.dataframe(split_table, use_container_width=True)
