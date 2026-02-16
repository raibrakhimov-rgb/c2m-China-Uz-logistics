import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go


# ================= CONFIG =================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

st.markdown("""
<style>
body {
    background-color: #f8fafc;
}

.block-container {
    padding-top: 1rem;
}

.metric-card {
    background: white;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

thead tr th {
    position: sticky;
    top: 0;
    background-color: #0f172a !important;
    color: white !important;
    z-index: 100;
}
</style>
""", unsafe_allow_html=True)


# ================= GOOGLE SHEET =================

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

    df.columns = df.columns.astype(str).str.strip()

    return df


df = load_data()


# ================= FIND COLS =================

def find_col(names):
    for col in df.columns:
        for n in names:
            if n.lower() in col.lower():
                return col
    return None


COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_AWB = find_col(["awb"])
COL_PROJECT = find_col(["project"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_SPLIT = find_col(["дроб"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])


# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

for c in [COL_DATE, COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")


df = df.dropna(subset=[COL_DATE, COL_WEIGHT])


# ================= TITLE =================

st.title("✈️ China → Uzbekistan Logistics Dashboard")


# ================= KPI =================

total_weight = df[COL_WEIGHT].sum()

total_flights = df[COL_AWB].nunique()

avg_weight = df.groupby(COL_AWB)[COL_WEIGHT].sum().mean()

if COL_ETD and COL_ATA:
    transit = (df[COL_ATA] - df[COL_ETD]).dt.days
    avg_transit = transit.mean()
else:
    avg_transit = None


col1, col2, col3, col4 = st.columns(4)

col1.metric("Общий вес (кг)", f"{total_weight:,.0f}")
col2.metric("Количество рейсов", f"{total_flights}")
col3.metric("Средний вес рейса", f"{avg_weight:,.0f}")

if avg_transit:
    col4.metric("Средний transit time (дней)", f"{avg_transit:.1f}")


# ================= FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio("Проект", projects, horizontal=True)

if project != "Все":
    df = df[df[COL_PROJECT] == project]


# ================= PERIOD =================

period = st.radio(
    "Период",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


# ================= CHART =================

chart_df = df.copy()

if period == "По дням":

    grouped = (
        chart_df
        .groupby(chart_df[COL_DATE].dt.date)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_DATE)
    )

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=grouped[COL_DATE],
        y=grouped[COL_WEIGHT],
        name="Вес"
    ))

    fig.add_trace(go.Scatter(
        x=grouped[COL_DATE],
        y=grouped[COL_WEIGHT],
        mode="lines+markers",
        name="Trend"
    ))

elif period == "По неделям":

    grouped = (
        chart_df
        .groupby(chart_df[COL_DATE].dt.to_period("W"))[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped[COL_DATE] = grouped[COL_DATE].astype(str)

    fig = px.bar(grouped, x=COL_DATE, y=COL_WEIGHT)

else:

    grouped = (
        chart_df
        .groupby(chart_df[COL_DATE].dt.to_period("M"))[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped[COL_DATE] = grouped[COL_DATE].astype(str)

    fig = px.bar(grouped, x=COL_DATE, y=COL_WEIGHT)


fig.update_layout(height=500)

st.plotly_chart(fig, use_container_width=True)


# ================= TABS =================

tab1, tab2 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии"
])


# ================= СПИСОК ПАРТИЙ =================

with tab1:

    table = df.copy()

    table = table.reset_index(drop=True)

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", table.index + 1)

    for c in [COL_DATE, COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
        if c:
            table[c] = table[c].dt.date


    search = st.text_input("Поиск")

    if search:
        table = table[
            table.astype(str)
            .apply(lambda x: x.str.contains(search, case=False))
            .any(axis=1)
        ]


    project_filter = st.selectbox(
        "Фильтр проект",
        ["Все"] + sorted(table[COL_PROJECT].dropna().unique())
    )

    if project_filter != "Все":
        table = table[table[COL_PROJECT] == project_filter]


    st.dataframe(table, use_container_width=True, height=700)


# ================= SPLIT =================

with tab2:

    if COL_SPLIT:

        split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split_df.groupby(COL_AWB):

            cartons = g[COL_CARTON].tolist()

            rows.append({

                "AWB": awb,
                "Flights": len(g),
                "Total cartons": sum(cartons),
                "Parts": ", ".join(map(str, cartons)),
                "ATA (при дроблении)": ", ".join(
                    g[COL_ATA].dt.date.astype(str)
                )

            })

        split_table = pd.DataFrame(rows)

        split_table.insert(0, "№", split_table.index + 1)

        st.dataframe(split_table, use_container_width=True)

    else:

        st.info("Нет дробленных партий")
