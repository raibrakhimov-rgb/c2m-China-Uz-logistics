import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="Executive Dashboard | China → Uzbekistan",
    layout="wide"
)

# =====================================================
# POWER BI STYLE CSS
# =====================================================

st.markdown("""
<style>

.block-container
{
    padding-top: 1rem;
}

.kpi-card
{
    background-color: white;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #e6e6e6;
}

.kpi-title
{
    font-size: 14px;
    color: gray;
}

.kpi-value
{
    font-size: 32px;
    font-weight: bold;
}

.section
{
    background-color: white;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #e6e6e6;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# LOAD DATA
# =====================================================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

START_ROW = 874


@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)

    df = pd.read_excel(BytesIO(r.content))

    df.columns = df.columns.astype(str).str.strip()

    df = df.iloc[START_ROW:].reset_index(drop=True)

    return df


df = load_data()


# =====================================================
# FIND COLUMNS
# =====================================================

def find_col(names):

    for col in df.columns:

        col_low = col.lower()

        for name in names:

            if name in col_low:
                return col

    return None


COL_PROJECT = find_col(["проект"])
COL_WEIGHT = find_col(["weight"])
COL_DATE = find_col(["outbound date"])
COL_VIA = find_col(["via"])
COL_ATD = find_col(["atd"])

# СТРОГО ATA (колонка N)
COL_ATA = None

for col in df.columns:

    if col.lower().strip() == "ata":
        COL_ATA = col
        break


# =====================================================
# CLEAN TYPES
# =====================================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce", dayfirst=True)

df[COL_ATD] = pd.to_datetime(df[COL_ATD], errors="coerce", dayfirst=True)

df[COL_ATA] = pd.to_datetime(df[COL_ATA], errors="coerce", dayfirst=True)

df = df.dropna(subset=[COL_DATE])


# =====================================================
# FILTERS
# =====================================================

st.sidebar.header("Фильтры")

projects = st.sidebar.multiselect(
    "Проект",
    sorted(df[COL_PROJECT].dropna().unique()),
    default=sorted(df[COL_PROJECT].dropna().unique())
)

filtered = df[df[COL_PROJECT].isin(projects)]


# =====================================================
# FIXED TRANSIT CALCULATION
# =====================================================

filtered["_ATA"] = pd.to_datetime(
    filtered[COL_ATA],
    errors="coerce",
    dayfirst=True
)

filtered["_ATD"] = pd.to_datetime(
    filtered[COL_ATD],
    errors="coerce",
    dayfirst=True
)

filtered["_TRANSIT"] = (
    filtered["_ATA"] - filtered["_ATD"]
).dt.days

valid_transit = filtered["_TRANSIT"].dropna()

valid_transit = valid_transit[valid_transit >= 0]

if len(valid_transit) > 0:

    avg_transit = int(round(valid_transit.mean(), 0))

else:

    avg_transit = 0


# =====================================================
# KPI CALCULATIONS
# =====================================================

total_weight = int(filtered[COL_WEIGHT].sum())

shipments = len(filtered)

avg_weight = int(filtered[COL_WEIGHT].mean())


# =====================================================
# HEADER
# =====================================================

st.title("Свод по рейсам Китай → Узбекистан")

st.write("")


# =====================================================
# KPI ROW
# =====================================================

c1, c2, c3, c4 = st.columns(4)


def kpi(col, title, value):

    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


kpi(c1, "Общий вес", f"{total_weight:,} кг")

kpi(c2, "Количество партий", f"{shipments:,}")

kpi(c3, "Средний вес", f"{avg_weight:,} кг")

kpi(c4, "Среднее транзитное время", f"{avg_transit} дней")


st.write("")
st.write("")


# =====================================================
# TREND CHART
# =====================================================

st.markdown('<div class="section">', unsafe_allow_html=True)

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

trend["Дата"] = trend["Дата"].dt.strftime("%d-%m-%Y")

fig = px.bar(
    trend,
    x="Дата",
    y="Вес",
    text="Вес"
)

fig.update_layout(
    height=400,
    plot_bgcolor="white"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# BREAKDOWN
# =====================================================

col1, col2 = st.columns(2)

with col1:

    st.markdown('<div class="section">', unsafe_allow_html=True)

    st.subheader("Объём по проектам")

    proj = (
        filtered
        .groupby(COL_PROJECT)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    st.plotly_chart(
        px.bar(proj, x=COL_PROJECT, y=COL_WEIGHT),
        use_container_width=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


with col2:

    st.markdown('<div class="section">', unsafe_allow_html=True)

    st.subheader("Объём по транзитным городам Китая")

    via = (
        filtered
        .groupby(COL_VIA)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    st.plotly_chart(
        px.pie(via, names=COL_VIA, values=COL_WEIGHT),
        use_container_width=True
    )

    st.markdown('</div>', unsafe_allow_html=True)
