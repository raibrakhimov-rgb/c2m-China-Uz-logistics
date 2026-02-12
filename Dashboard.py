import streamlit as st
import pandas as pd

# ================= CONFIG =================

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"

# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(SHEET_URL)
    return df

df = load_data()

# ================= PREPARE =================

# Переименуем колонки для удобства
df.columns = [
    "Outbound_carton",
    "Outbound_weight",
    "Outbound_date",
    "AWB",
    "Flight",
    "ETD",
    "Comment",
    "ETA",
    "ATD",
    "ATA",
    "ATA_ext",
    "Plan_transit"
]

# Даты
date_cols = ["Outbound_date", "ETD", "ETA", "ATD", "ATA"]

for col in date_cols:
    df[col] = pd.to_datetime(df[col], errors="coerce")

# Статус

def get_status(row):
    if pd.notna(row["ATA"]):
        return "Delivered"
    if pd.notna(row["ATD"]):
        return "In Transit"
    if pd.notna(row["ETD"]):
        return "Scheduled"
    return "Pending"

df["Status"] = df.apply(get_status, axis=1)

# ================= UI =================

st.set_page_config(
    page_title="China Logistics Dashboard",
    layout="wide"
)

st.title("✈️ China Logistics Dashboard")

# ================= SIDEBAR =================

st.sidebar.header("Фильтры")

min_date = df["ETD"].min()
max_date = df["ETD"].max()

date_from = st.sidebar.date_input(
    "ETD от",
    min_date
)

date_to = st.sidebar.date_input(
    "ETD до",
    max_date
)

flights = st.sidebar.multiselect(
    "Рейс",
    df["Flight"].dropna().unique()
)

statuses = st.sidebar.multiselect(
    "Статус",
    df["Status"].unique(),
    default=df["Status"].unique()
)

comments = st.sidebar.multiselect(
    "Комментарий",
    df["Comment"].dropna().unique()
)

# ================= FILTER =================

filtered = df.copy()

filtered = filtered[
    (filtered["ETD"] >= pd.to_datetime(date_from)) &
    (filtered["ETD"] <= pd.to_datetime(date_to))
]

if flights:
    filtered = filtered[filtered["Flight"].isin(flights)]

if comments:
    filtered = filtered[filtered["Comment"].isin(comments)]

filtered = filtered[filtered["Status"].isin(statuses)]

# ================= KPI =================

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("📦 Партии", len(filtered))
c2.metric("⚖️ Вес (кг)", int(filtered["Outbound_weight"].sum()))
c3.metric("✈️ В пути", len(filtered[filtered["Status"]=="In Transit"]))
c4.metric("⏳ Запланировано", len(filtered[filtered["Status"]=="Scheduled"]))
c5.metric("🏭 Доставлено", len(filtered[filtered["Status"]=="Delivered"]))

# ================= CHART =================

st.subheader("📈 Вылеты по ETD")

chart = (
    filtered
    .groupby("ETD")["Outbound_weight"]
    .sum()
)

st.line_chart(chart)

# ================= TABLE =================

st.subheader("📋 Партии")

show_cols = [
    "AWB",
    "Flight",
    "ETD",
    "ETA",
    "Status",
    "Outbound_weight",
    "Comment"
]

st.dataframe(
    filtered[show_cols]
    .sort_values("ETD", ascending=False),
    use_container_width=True
)

# ================= DOWNLOAD =================

st.download_button(
    "⬇️ Скачать CSV",
    filtered.to_csv(index=False),
    "china_logistics.csv",
    "text/csv"
)
