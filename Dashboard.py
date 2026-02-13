import streamlit as st
import pandas as pd
import altair as alt
import requests
from io import StringIO


# ================== CONFIG ==================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"


START_ROW = 881   # с какой строки начинать (0 = первая)
HEADER_ROW = 1    # где заголовки (строка 2)


# ================== LOAD DATA ==================

@st.cache_data(ttl=600)
def load_data():

    r = requests.get(CSV_URL)
    r.encoding = "utf-8"

    df = pd.read_csv(
        StringIO(r.text),
        header=1
    )

    # Убираем пустые колонки
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # Чистим названия
    df.columns = df.columns.str.strip()

    return df


df = load_data()

st.write("Колонки:", list(df.columns))
st.dataframe(df.head(20))


# ================== HELPERS ==================

def find_col(keywords):
    for col in df.columns:
        name = col.lower()
        for k in keywords:
            if k in name:
                return col
    return None


# ================== FIND COLUMNS ==================

COL_WEIGHT = find_col(["weight", "вес", "kg"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_CARTON = find_col(["carton"])
COL_SPLIT = find_col(["дроб"])
COL_PROJECT = find_col(["проект", "project"])
COL_COMMENT = find_col(["коммент", "comment"])


REQUIRED = {
    "Weight": COL_WEIGHT,
    "ETD": COL_ETD,
    "ATD": COL_ATD,
    "ETA": COL_ETA,
    "ATA": COL_ATA,
    "AWB": COL_AWB,
    "Carton": COL_CARTON,
    "Project": COL_PROJECT,
}

missing = [k for k, v in REQUIRED.items() if v is None]

if missing:
    st.error("❌ Не найдены обязательные колонки")
    st.write("Отсутствуют:", missing)
    st.write("Найденные:", list(df.columns))
    st.stop()


# ================== CLEAN ==================

for col in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    df[col] = pd.to_datetime(df[col], errors="coerce")

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

df = df.dropna(subset=[COL_ETD])


# ================== PROJECT FILTER ==================

st.title("✈️ Вылеты Китай → Узбекистан")

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

selected_project = st.radio(
    "",
    projects,
    horizontal=True
)

if selected_project != "Все":
    df = df[df[COL_PROJECT] == selected_project]


# ================== GROUPING ==================

group = st.radio(
    "",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


# ================== GROUP DATA ==================

chart_df = df.copy()


# --- DAYS ---
if group == "По дням":

    chart_df["period"] = chart_df[COL_ETD].dt.strftime("%d.%m")

    grouped = chart_df.groupby("period", sort=False)[COL_WEIGHT].sum().reset_index()


# --- WEEKS ---
elif group == "По неделям":

    chart_df["week"] = chart_df[COL_ETD].dt.to_period("W-MON")

    grouped = (
        chart_df
        .groupby("week")[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped["start"] = grouped["week"].dt.start_time
    grouped["end"] = grouped["week"].dt.end_time

    grouped["period"] = (
        grouped["start"].dt.strftime("%d.%m") +
        "-" +
        grouped["end"].dt.strftime("%d.%m")
    )

    grouped = grouped[["period", COL_WEIGHT]]


# --- MONTHS ---
else:

    MONTHS_RU = {
        1: "январь", 2: "февраль", 3: "март", 4: "апрель",
        5: "май", 6: "июнь", 7: "июль", 8: "август",
        9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
    }

    chart_df["year"] = chart_df[COL_ETD].dt.year
    chart_df["month"] = chart_df[COL_ETD].dt.month

    grouped = (
        chart_df
        .groupby(["year", "month"])[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped["period"] = grouped.apply(
        lambda x: f"{MONTHS_RU[x['month']]} {int(x['year'])}",
        axis=1
    )

    grouped = grouped[["period", COL_WEIGHT]]


grouped["idx"] = range(len(grouped))


# ================== BAR CHART ==================

chart = (
    alt.Chart(grouped)
    .mark_bar(size=38)
    .encode(
        x=alt.X(
            "idx:O",
            axis=alt.Axis(
                labelAngle=-90,
                labelExpr="datum.label",
                labelOverlap=False
            )
        ),
        y=alt.Y(f"{COL_WEIGHT}:Q", title="Вес (кг)"),
        tooltip=["period", COL_WEIGHT]
    )
    .transform_calculate(
        label="datum.period"
    )
    .properties(height=420)
)

st.altair_chart(chart, use_container_width=True)


# ================== SPLITS ==================

split_df = df[df[COL_SPLIT].astype(str).str.contains("да", case=False, na=False)]

split_groups = split_df.groupby(COL_AWB)

rows = []

for awb, g in split_groups:

    if len(g) < 2:
        continue

    cartons = list(g[COL_CARTON].dropna().astype(int))

    rows.append({
        "Booking/AWB NO": awb,
        "Q-ty of flights": len(g),
        "Total No of cartons": sum(cartons),
        "Q-ty of separate cartons": ", ".join(map(str, cartons))
    })


split_table = pd.DataFrame(rows)


# ================== TABS ==================

tab1, tab2, tab3 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии",
    "📊 Данные"
])


# ================== LIST ==================

with tab1:

    table = df.copy()

    table["ATA_ext"] = table[COL_ATA].dt.strftime("%H:%M")

    table = table.sort_values(COL_ETD, ascending=False)

    table = table.rename(columns={
        COL_AWB: "AWB",
        COL_WEIGHT: "Weight (kg)",
        COL_ETD: "ETD",
        COL_ATD: "ATD",
        COL_ETA: "ETA",
        COL_ATA: "ATA",
        COL_PROJECT: "Project"
    })

    table["ETD"] = table["ETD"].dt.strftime("%d.%m.%Y")
    table["ATD"] = table["ATD"].dt.strftime("%d.%m.%Y")
    table["ETA"] = table["ETA"].dt.strftime("%d.%m.%Y")
    table["ATA"] = table["ATA"].dt.strftime("%d.%m.%Y")

    table = table.reset_index(drop=True)
    table.index += 1

    st.dataframe(table, use_container_width=True)


# ================== SPLITS TAB ==================

with tab2:

    if split_table.empty:
        st.info("Нет дробленных партий")
    else:

        split_table = split_table.reset_index(drop=True)
        split_table.index += 1

        split_table.insert(0, "№", split_table.index)

        st.dataframe(split_table, use_container_width=True)


# ================== RAW ==================

with tab3:

    st.dataframe(df, use_container_width=True)




