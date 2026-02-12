import streamlit as st
import pandas as pd


SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"


# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():
    return pd.read_csv(SHEET_URL, header=1)


df = load_data()

st.set_page_config("China Logistics Dashboard", layout="wide")
st.title("✈️ China Logistics Control Center")

if df.empty:
    st.stop()


# ================= CLEAN =================

df.columns = df.columns.str.strip()


def find_col(keys):
    for col in df.columns:
        for k in keys:
            if k.lower() in col.lower():
                return col
    return None


COL_WEIGHT = find_col(["weight", "kg", "вес"])
COL_FLIGHT = find_col(["flight"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb", "booking"])
COL_COMMENT = find_col(["comment", "коммент"])
COL_POD = find_col(["pod"])


# ================= DATES =================

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")


# ================= CLEAN WEIGHT =================

if COL_WEIGHT:
    df[COL_WEIGHT] = (
        df[COL_WEIGHT]
        .astype(str)
        .str.replace(r"[^\d\.]", "", regex=True)
    )

    df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")


# ================= FILTER 2026+ =================

if COL_ETD:
    df = df[df[COL_ETD].dt.year >= 2026]


# ================= STATUS =================

def get_status(row):

    if COL_ATA and pd.notna(row[COL_ATA]):
        return "Delivered"

    if COL_ATD and pd.notna(row[COL_ATD]):
        return "In Transit"

    if COL_ETD and pd.notna(row[COL_ETD]):
        return "Scheduled"

    return "Pending"


df["Status"] = df.apply(get_status, axis=1)


# ================= PLAN / FACT =================

if COL_ETD and COL_ATD:
    df["Delay_Departure_h"] = (
        (df[COL_ATD] - df[COL_ETD])
        .dt.total_seconds() / 3600
    )

if COL_ETA and COL_ATA:
    df["Delay_Arrival_h"] = (
        (df[COL_ATA] - df[COL_ETA])
        .dt.total_seconds() / 3600
    )


# ================= TRANSIT =================

if COL_ATD and COL_ATA:

    df["Transit_days"] = (
        (df[COL_ATA] - df[COL_ATD])
        .dt.total_seconds() / 86400
    )


# ================= SLA =================

SLA_LIMIT = 24  # часов


if "Delay_Arrival_h" in df.columns:

    df["SLA_OK"] = df["Delay_Arrival_h"] <= SLA_LIMIT


# ================= SIDEBAR =================

st.sidebar.header("Фильтры")

if COL_FLIGHT:
    flights = st.sidebar.multiselect(
        "Рейс",
        sorted(df[COL_FLIGHT].dropna().unique())
    )

    if flights:
        df = df[df[COL_FLIGHT].isin(flights)]


if COL_COMMENT:
    tags = st.sidebar.multiselect(
        "UZUM / MPO",
        df[COL_COMMENT].dropna().unique()
    )

    if tags:
        df = df[df[COL_COMMENT].isin(tags)]


if COL_POD:
    pods = st.sidebar.multiselect(
        "POD",
        df[COL_POD].dropna().unique()
    )

    if pods:
        df = df[df[COL_POD].isin(pods)]


# ================= KPI =================

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", len(df))

c2.metric(
    "⚖️ Вес (кг)",
    int(df[COL_WEIGHT].sum()) if COL_WEIGHT else 0
)

c3.metric("✈️ В пути", len(df[df["Status"] == "In Transit"]))

c4.metric("🏭 Доставлено", len(df[df["Status"] == "Delivered"]))


if "Transit_days" in df.columns:
    c5.metric("⏱ Средний транзит (дн)", round(df["Transit_days"].mean(), 1))
else:
    c5.metric("⏱ Средний транзит", "-")


if "SLA_OK" in df.columns:
    sla = round(df["SLA_OK"].mean() * 100, 1)
    c6.metric("🎯 SLA %", sla)
else:
    c6.metric("🎯 SLA", "-")


# ================= TABS =================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Вылеты",
    "✈️ Авиакомпании",
    "🌍 POD",
    "⏰ Просрочки",
    "📋 Партии"
])


# ================= TAB 1 =================

with tab1:

    st.subheader("Вылеты по дням")

    if COL_ETD and COL_WEIGHT:

        chart = (
            df
            .groupby(df[COL_ETD].dt.date)[COL_WEIGHT]
            .sum()
            .sort_index()
        )

        st.line_chart(chart)


# ================= TAB 2 =================

with tab2:

    st.subheader("По авиакомпаниям")

    if COL_FLIGHT:

        air = (
            df
            .groupby(COL_FLIGHT)
            .agg({
                COL_WEIGHT: "sum",
                "Status": "count"
            })
            .rename(columns={
                COL_WEIGHT: "Weight",
                "Status": "Shipments"
            })
        )

        st.dataframe(air.sort_values("Weight", ascending=False))


# ================= TAB 3 =================

with tab3:

    st.subheader("По POD")

    if COL_POD:

        pod = (
            df
            .groupby(COL_POD)[COL_WEIGHT]
            .sum()
        )

        st.bar_chart(pod)


# ================= TAB 4 =================

with tab4:

    st.subheader("Просрочки > 24ч")

    if "Delay_Arrival_h" in df.columns:

        delay = df[df["Delay_Arrival_h"] > SLA_LIMIT]

        st.dataframe(delay)


# ================= TAB 5 =================

with tab5:

    st.subheader("Список партий")

    cols = []

    for c in [
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ETA,
        COL_ATD,
        COL_ATA,
        COL_WEIGHT,
        "Status",
        COL_COMMENT
    ]:
        if c and c in df.columns:
            cols.append(c)

    if "Transit_days" in df.columns:
        cols.append("Transit_days")

    if "Delay_Arrival_h" in df.columns:
        cols.append("Delay_Arrival_h")

    st.dataframe(
        df[cols].sort_values(COL_ETD, ascending=False),
        use_container_width=True
    )


# ================= DOWNLOAD =================

st.download_button(
    "⬇️ Скачать отчёт",
    df.to_csv(index=False),
    "china_logistics_full_2026.csv",
    "text/csv"
)
