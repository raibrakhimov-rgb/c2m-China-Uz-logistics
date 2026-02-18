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
    padding-bottom: 1rem;
}

.kpi-card
{
    background-color: #ffffff;
    padding: 18px;
    border-radius: 10px;
    border: 1px solid #e6e6e6;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.kpi-title
{
    font-size: 14px;
    color: #666;
}

.kpi-value
{
    font-size: 28px;
    font-weight: bold;
    color: #111;
}

.section
{
    background-color: #ffffff;
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

def find(names):

    for col in df.columns:

        c = col.lower()

        for name in names:

            if name in c:
                return col

    return None


COL_PROJECT = find(["проект"])
COL_WEIGHT = find(["weight"])
COL_DATE = find(["outbound date"])
COL_VIA = find(["via"])
COL_ATD = find(["atd"])

COL_ATA = None
for col in df.columns:
    if col.lower().strip() == "ata":
        COL_ATA = col


# =====================================================
# CLEAN TYPES
# =====================================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

df[COL_ATD] = pd.to_datetime(df[COL_ATD], errors="coerce")

df[COL_ATA] = pd.to_datetime(df[COL_ATA], errors="coerce")

df["Transit"] = (df[COL_ATA] - df[COL_ATD]).dt.days

df = df.dropna(subset=[COL_DATE])


# =====================================================
# FILTERS
# =====================================================

st.sidebar.header("Filters")

projects = st.sidebar.multiselect(
    "Project",
    df[COL_PROJECT].dropna().unique(),
    default=df[COL_PROJECT].dropna().unique()
)

filtered = df[df[COL_PROJECT].isin(projects)]


# =====================================================
# KPI CALCULATIONS
# =====================================================

total_weight = int(filtered[COL_WEIGHT].sum())

shipments = len(filtered)

avg_weight = int(filtered[COL_WEIGHT].mean())

avg_transit = int(filtered["Transit"].mean())


# =====================================================
# HEADER
# =====================================================

st.title("Executive Dashboard | China → Uzbekistan")

st.write("")


# =====================================================
# KPI ROW (Power BI Style)
# =====================================================

c1, c2, c3, c4 = st.columns(4)

def kpi(col, title, value):

    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


kpi(c1, "Total Weight", f"{total_weight:,} kg")
kpi(c2, "Shipments", f"{shipments:,}")
kpi(c3, "Average Weight", f"{avg_weight:,} kg")
kpi(c4, "Transit Time", f"{avg_transit} days")


st.write("")
st.write("")


# =====================================================
# TREND CHART
# =====================================================

st.markdown('<div class="section">', unsafe_allow_html=True)

st.subheader("Shipment Volume Trend")

trend = (
    filtered
    .sort_values(COL_DATE)
    .groupby(filtered[COL_DATE].dt.date)[COL_WEIGHT]
    .sum()
    .reset_index()
)

trend.columns = ["Date", "Weight"]

fig = px.bar(
    trend,
    x="Date",
    y="Weight",
    text="Weight"
)

fig.update_layout(
    plot_bgcolor="white",
    height=400
)

st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# BREAKDOWN ROW
# =====================================================

col1, col2 = st.columns(2)

with col1:

    st.markdown('<div class="section">', unsafe_allow_html=True)

    st.subheader("Volume by Project")

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

    st.subheader("Volume by Transit City")

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


# =====================================================
# TABLE
# =====================================================

st.markdown('<div class="section">', unsafe_allow_html=True)

st.subheader("Shipments")

filtered_display = filtered.copy()

filtered_display.insert(0, "№", range(1, len(filtered_display)+1))

st.dataframe(filtered_display, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
