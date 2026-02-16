import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.graph_objects as go
import plotly.express as px

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

# =====================================
# STYLE
# =====================================

st.markdown("""
<style>

html, body, [data-testid="stApp"] {
    background-color: #f4f6fa;
}

.block-container {
    padding-top: 20px;
}

.kpi-card {
    background: white;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

</style>
""", unsafe_allow_html=True)

# =====================================
# LOAD DATA
# =====================================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

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


COL_WEIGHT = find_col(["weight"])
COL_DATE = find_col(["outbound date"])
COL_PROJECT = find_col(["project", "проект"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_SPLIT = find_col(["дроб"])

# types

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

if COL_ATD:
    df[COL_ATD] = pd.to_datetime(df[COL_ATD], errors="coerce")

if COL_ATA:
    df[COL_ATA] = pd.to_datetime(df[COL_ATA], errors="coerce")

df = df.dropna(subset=[COL_DATE])

# =====================================
# TITLE
# =====================================

st.title("✈️ China → Uzbekistan Logistics Dashboard")

# =====================================
# KPI BLOCK
# =====================================

total_weight = int(df[COL_WEIGHT].sum())

total_flights = df[COL_AWB].nunique()

avg_weight = int(df[COL_WEIGHT].mean())

if COL_ATD and COL_ATA:
    transit = (df[COL_ATA] - df[COL_ATD]).dt.days
    avg_transit = round(transit.mean(),1)
else:
    avg_transit = 0

c1,c2,c3,c4 = st.columns(4)

c1.markdown(f"""
<div class="kpi-card">
<h4>Общий вес</h4>
<h2>{total_weight:,} кг</h2>
</div>
""", unsafe_allow_html=True)

c2.markdown(f"""
<div class="kpi-card">
<h4>Количество рейсов</h4>
<h2>{total_flights}</h2>
</div>
""", unsafe_allow_html=True)

c3.markdown(f"""
<div class="kpi-card">
<h4>Средний вес</h4>
<h2>{avg_weight} кг</h2>
</div>
""", unsafe_allow_html=True)

c4.markdown(f"""
<div class="kpi-card">
<h4>Средний transit time</h4>
<h2>{avg_transit} дней</h2>
</div>
""", unsafe_allow_html=True)

st.write("")

# =====================================
# FILTER
# =====================================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT]==project]

period = st.radio(
    "Период",
    ["По дням","По неделям","По месяцам"],
    horizontal=True
)

# =====================================
# GROUP DATA
# =====================================

if period=="По дням":

    grouped = df.groupby(
        df[COL_DATE].dt.date
    )[COL_WEIGHT].sum().reset_index()

    grouped["date"] = pd.to_datetime(grouped[COL_DATE])

    grouped = grouped.sort_values("date")

    grouped = grouped.tail(30)

    x = grouped["date"]

elif period=="По неделям":

    grouped = df.groupby(
        df[COL_DATE].dt.to_period("W")
    )[COL_WEIGHT].sum().reset_index()

    grouped["date"] = grouped[COL_DATE].dt.start_time

    grouped = grouped.sort_values("date")

    x = grouped["date"]

else:

    grouped = df.groupby(
        df[COL_DATE].dt.to_period("M")
    )[COL_WEIGHT].sum().reset_index()

    grouped["date"] = grouped[COL_DATE].dt.start_time

    grouped = grouped.sort_values("date")

    x = grouped["date"]

# =====================================
# CHART
# =====================================

fig = go.Figure()

fig.add_bar(
    x=x,
    y=grouped[COL_WEIGHT],
    name="Weight",
)

fig.add_scatter(
    x=x,
    y=grouped[COL_WEIGHT],
    mode="lines+markers",
    name="Trend"
)

fig.update_layout(
    height=500,
    plot_bgcolor="white",
    paper_bgcolor="white",
    xaxis=dict(
        rangeslider=dict(visible=True),
        type="date"
    ),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================
# SPLIT PARTIES
# =====================================

st.subheader("📦 Дробленные партии")

if COL_SPLIT:

    split_df = df[df[COL_SPLIT].astype(str).str.lower()=="да"]

    rows=[]

    for awb,g in split_df.groupby(COL_AWB):

        if len(g)<2:
            continue

        cartons=g["Outbound carton"].tolist()

        rows.append({
            "AWB":awb,
            "Flights":len(g),
            "Cartons total":sum(cartons),
            "Cartons split":",".join(map(str,cartons))
        })

    split_table=pd.DataFrame(rows)

    split_table.insert(0,"№",split_table.index+1)

    st.dataframe(split_table,use_container_width=True)

else:

    st.info("Нет дробленных партий")
