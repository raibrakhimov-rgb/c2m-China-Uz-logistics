import streamlit as st
import pandas as pd


SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"


# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():
    return pd.read_csv(SHEET_URL, header=2)


df = load_data()

st.set_page_config("China Logistics Dashboard", layout="wide")
st.title("✈️ China Logistics Dashboard")

if df.empty:
    st.error("Нет данных")
    st.stop()


# ================= CLEAN =================

df.columns = df.columns.str.strip()


# ================= FIND COLUMNS =================

def find_col(keys):
    for col in df.columns:
        for k in keys:
            if k.lower() in col.lower():
                return col
    return None


COL_WEIGHT = find_col(["weight", "вес", "kg"])
COL_FLIGHT = find_col(["flight", "рейс"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb", "booking"])
COL_COMMENT = find_col(["comment", "коммент"])
COL_DATE = find_col(["outbound date", "date", "дата"])


# ================= DATES =================

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA, COL_DATE]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")


# ================= FILTER 2026+ =================

BASE_DATE = None

if COL_ETD:
    BASE_DATE = COL_ETD
elif COL_DATE:
    BASE_DATE = COL_DATE

if BASE_DATE:
    df = df[df[BASE_DATE].dt.year >= 2026]


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


# ================= SIDEBAR =================

st.sidebar.header("Фильтры")

if COL_ETD:

    min_d = df[COL_ETD].min()
    max_d = df[COL_ETD].max()

    date_from = st.sidebar.date_input("ETD от", min_d)
    date_to = st.sidebar.date_input("ETD до", max_d)

    df = df[
        (df[COL_ETD] >= pd.to_datetime(date_from)) &
        (df[COL_ETD] <= pd.to_datetime(date_to))
    ]


if COL_FLIGHT:

    flights = st.sidebar.multiselect(
        "Рейс",
        sorted(df[COL_FLIGHT].dropna().unique())
    )

    if flights:
        df = df[df[COL_FLIGHT].isin(flights)]


# ================= KPI =================

c1, c2, c3, c4 = st.columns(4)

c1.metric("📦 Партии", len(df))


if COL_WEIGHT:
    total_weight = pd.to_numeric(df[COL_WEIGHT], errors="coerce").sum()
else:
    total_weight = 0

c2.metric("⚖️ Вес (кг)", int(total_weight))

c3.metric("✈️ В пути", len(df[df["Status"] == "In Transit"]))
c4.metric("🏭 Доставлено", len(df[df["Status"] == "Delivered"]))


# ================= CHART =================

st.subheader("📈 Вылеты (по ETD)")

if COL_ETD and COL_WEIGHT:

    chart_df = (
        df
        .groupby(df[COL_ETD].dt.date)[COL_WEIGHT]
        .sum()
    )

    if not chart_df.empty:
        st.line_chart(chart_df)
    else:
        st.warning("Нет данных для графика")

else:
    st.warning("Нет данных для графика")


# ================= TABLE =================

st.subheader("📋 Партии")


display_cols = []

for c in [
    COL_AWB,
    COL_FLIGHT,
    COL_ETD,
    COL_ETA,
    COL_WEIGHT,
    "Status",
    COL_COMMENT
]:
    if c and c in df.columns:
        display_cols.append(c)


if "Status" not in display_cols:
    display_cols.append("Status")


table = df[display_cols].copy()


# Красивые заголовки
rename_map = {}

if COL_AWB:
    rename_map[COL_AWB] = "AWB"

if COL_FLIGHT:
    rename_map[COL_FLIGHT] = "Flight"

if COL_ETD:
    rename_map[COL_ETD] = "ETD"

if COL_ETA:
    rename_map[COL_ETA] = "ETA"

if COL_WEIGHT:
    rename_map[COL_WEIGHT] = "Weight (kg)"

if COL_COMMENT:
    rename_map[COL_COMMENT] = "Comment"


table = table.rename(columns=rename_map)


st.dataframe(
    table.sort_values("ETD", ascending=False),
    use_container_width=True
)


# ================= DOWNLOAD =================

st.download_button(
    "⬇️ Скачать CSV",
    df.to_csv(index=False),
    "china_logistics_2026.csv",
    "text/csv"
)

