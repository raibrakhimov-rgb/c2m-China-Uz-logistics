# ================= IMPORTS =================

import streamlit as st
import pandas as pd
import requests
from io import StringIO
import matplotlib.pyplot as plt
from datetime import datetime
import locale


# ================= SETTINGS =================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

# 👉 ВСТАВЬ СЮДА СВОЮ ССЫЛКУ CSV
SHEET_URL = "PASTE_YOUR_CSV_LINK_HERE"


# ================= LOAD DATA =================

@st.cache_data
def load_data():

    r = requests.get(SHEET_URL)

    if r.status_code != 200:
        st.error("❌ Не удалось загрузить таблицу")
        st.stop()

    # Главный фикс: правильный header
    df = pd.read_csv(
        StringIO(r.text),
        skiprows=1,
        header=0
    )

    df = df.dropna(how="all")

    df.columns = df.columns.str.strip()

    return df


df = load_data()


# ================= DEBUG =================

with st.expander("🛠 Debug: Колонки"):
    st.write(df.columns.tolist())
    st.dataframe(df.head(10))


# ================= COLUMN FINDER =================

def find_col(keys):

    for col in df.columns:
        name = col.lower()

        for k in keys:
            if k in name:
                return col

    return None


COL_WEIGHT = find_col(["weight", "вес", "kg"])
COL_DATE = find_col(["outbound", "date"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_CARTON = find_col(["carton"])
COL_PROJECT = find_col(["проект", "project"])
COL_SPLIT = find_col(["дроб"])


REQUIRED = [
    COL_WEIGHT,
    COL_DATE,
    COL_AWB,
    COL_CARTON,
    COL_PROJECT
]

if any(c is None for c in REQUIRED):

    st.error("❌ Не найдены обязательные колонки")

    st.write("Найденные:", df.columns.tolist())

    st.stop()


# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")


df = df.dropna(subset=[COL_DATE, COL_WEIGHT])


# ================= TITLE =================

st.title("✈️ Вылеты Китай → Узбекистан")


# ================= PROJECT FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

proj = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if proj != "Все":
    df = df[df[COL_PROJECT] == proj]


# ================= GROUP SELECT =================

group_mode = st.radio(
    "Группировка:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


# ================= GROUPING =================

chart_df = df.copy()

# ДНИ
if group_mode == "По дням":

    chart_df["label"] = chart_df[COL_DATE].dt.strftime("%d.%m")

    grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()


# НЕДЕЛИ
elif group_mode == "По неделям":

    chart_df["week_start"] = chart_df[COL_DATE] - pd.to_timedelta(
        chart_df[COL_DATE].dt.weekday, unit="D"
    )

    chart_df["week_end"] = chart_df["week_start"] + pd.Timedelta(days=6)

    chart_df["label"] = (
        chart_df["week_start"].dt.strftime("%d.%m") +
        "-" +
        chart_df["week_end"].dt.strftime("%d.%m")
    )

    grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()


# МЕСЯЦЫ
else:

    months = {
        1: "январь", 2: "февраль", 3: "март",
        4: "апрель", 5: "май", 6: "июнь",
        7: "июль", 8: "август", 9: "сентябрь",
        10: "октябрь", 11: "ноябрь", 12: "декабрь"
    }

    chart_df["month"] = chart_df[COL_DATE].dt.month
    chart_df["year"] = chart_df[COL_DATE].dt.year

    chart_df["label"] = chart_df["month"].map(months) + " " + chart_df["year"].astype(str)

    grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()


# ================= CHART =================

fig, ax = plt.subplots(figsize=(14, 5))

ax.bar(
    range(len(grouped)),
    grouped[COL_WEIGHT],
    width=0.8
)

ax.set_ylabel("Вес (кг)")
ax.set_xlabel("")

ax.set_xticks(range(len(grouped)))
ax.set_xticklabels(grouped["label"], rotation=90)

plt.tight_layout()

st.pyplot(fig)


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии",
    "📊 Данные"
])


# ================= BATCH LIST =================

with tab1:

    table = df.copy().reset_index(drop=True)

    table.insert(0, "№", range(1, len(table) + 1))

    st.dataframe(table, use_container_width=True)


# ================= SPLIT SHIPMENTS =================

with tab2:

    if not COL_SPLIT:

        st.info("Нет колонки 'Дробление'")

    else:

        split_df = df.copy()

        split_df["is_split"] = split_df[COL_SPLIT].astype(str).str.lower() == "да"

        groups = []

        for awb, g in split_df.groupby(COL_AWB):

            parts = g[g["is_split"]]

            if len(parts) >= 2:

                cartons = parts[COL_CARTON].tolist()

                groups.append({
                    "AWB": awb,
                    "Q-ty of flights": len(parts),
                    "Total No of cartons": sum(cartons),
                    "Q-ty of separate cartons": ", ".join(map(str, cartons))
                })

        if not groups:

            st.info("Дробленных партий не найдено")

        else:

            split_table = pd.DataFrame(groups)

            split_table.insert(0, "№", range(1, len(split_table) + 1))

            st.dataframe(split_table, use_container_width=True)


# ================= RAW =================

with tab3:

    st.dataframe(df, use_container_width=True)
