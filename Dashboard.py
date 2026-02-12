import streamlit as st
import pandas as pd

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"


def load_data():
    try:
        return pd.read_csv(SHEET_URL)
    except Exception as e:
        st.error("Ошибка загрузки данных")
        st.exception(e)
        return pd.DataFrame()


df = load_data()

st.set_page_config("China Logistics Dashboard", layout="wide")

st.title("✈️ China Logistics Dashboard")

if df.empty:
    st.stop()

# Очистка колонок
df.columns = df.columns.str.strip()

# Показываем колонки
with st.expander("📌 Список колонок"):
    st.write(df.columns.tolist())


# Автоопределение колонок
def find_col(name_list):
    for col in df.columns:
        for name in name_list:
            if name.lower() in col.lower():
                return col
    return None


COL_WEIGHT = find_col(["weight"])
COL_FLIGHT = find_col(["flight"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_COMMENT = find_col(["comment", "коммент"])


# Преобразование дат
for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")


# Статус
def get_status(row):
    if COL_ATA and pd.notna(row[COL_ATA]):
        return "Delivered"
    if COL_ATD and pd.notna(row[COL_ATD]):
        return "In Transit"
    if COL_ETD and pd.notna(row[COL_ETD]):
        return "Scheduled"
    return "Pending"


df["Status"] = df.apply(get_status, axis=1)


# Sidebar
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
        df[COL_FLIGHT].dropna().unique()
    )

    if flights:
        df = df[df[COL_FLIGHT].isin(flights)]


# KPI
c1, c2, c3, c4 = st.columns(4)

c1.metric("📦 Партии", len(df))

if COL_WEIGHT:
    c2.metric("⚖️ Вес (кг)", int(df[COL_WEIGHT].sum()))
else:
    c2.metric("⚖️ Вес (кг)", 0)

c3.metric("✈️ В пути", len(df[df["Status"] == "In Transit"]))
c4.metric("🏭 Доставлено", len(df[df["Status"] == "Delivered"]))


# График
st.subheader("📈 Вылеты")

if COL_ETD and COL_WEIGHT:

    chart = df.groupby(COL_ETD)[COL_WEIGHT].sum()
    st.line_chart(chart)

else:
    st.warning("Нет данных для графика")


# Таблица
st.subheader("📋 Партии")

st.dataframe(df, use_container_width=True)


# Скачать
st.download_button(
    "⬇️ Скачать CSV",
    df.to_csv(index=False),
    "logistics.csv",
    "text/csv"
)

