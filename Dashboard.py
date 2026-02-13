import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import matplotlib.pyplot as plt
from datetime import timedelta


# ================= CONFIG =================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

# ТВОИ ДАННЫЕ (НЕ МЕНЯТЬ, ЕСЛИ ТАБЛИЦА ТА ЖЕ)
SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

XLSX_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"


# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(XLSX_URL)
    r.raise_for_status()

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(XLSX_URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1   # заголовки во 2-й строке
    )

    # убираем пустые строки
    df = df.dropna(how="all")

    # убираем Unnamed
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    # чистим названия
    df.columns = df.columns.astype(str).str.strip()

    # ================== ВАЖНО ==================
    # Берём только строки с 867 и ниже (нумерация с 1)
    df = df.iloc[866:].reset_index(drop=True)
    # ===========================================

    return df



df = load_data()


# ================= FIND COL =================

def find_col(keys):

    for col in df.columns:

        name = col.lower()

        for k in keys:
            if k in name:
                return col

    return None


# ================= MAP COLUMNS =================

COL_WEIGHT = find_col(["outbound weight", "weight", "kg", "вес"])
COL_CARTON = find_col(["outbound carton", "carton"])
COL_DATE = find_col(["outbound date", "date"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_PROJECT = find_col(["проект", "project"])
COL_SPLIT = find_col(["дроб"])


REQUIRED = [
    COL_WEIGHT,
    COL_CARTON,
    COL_DATE,
    COL_AWB,
    COL_PROJECT
]

if any(x is None for x in REQUIRED):

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

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")


# ================= PROJECT =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]


# ================= GROUP =================

group = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


# ================= GROUP DATA =================

chart_df = df.copy()


# --- DAYS ---
if group == "По дням":

    chart_df["label"] = chart_df[COL_DATE].dt.strftime("%d.%m")

    grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()


# --- WEEKS ---
elif group == "По неделям":

    chart_df["start"] = chart_df[COL_DATE] - pd.to_timedelta(
        chart_df[COL_DATE].dt.weekday, unit="D"
    )

    chart_df["end"] = chart_df["start"] + pd.Timedelta(days=6)

    chart_df["label"] = (
        chart_df["start"].dt.strftime("%d.%m") +
        "-" +
        chart_df["end"].dt.strftime("%d.%m")
    )

    grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()


# --- MONTHS ---
else:

    months = {
        1: "январь", 2: "февраль", 3: "март",
        4: "апрель", 5: "май", 6: "июнь",
        7: "июль", 8: "август", 9: "сентябрь",
        10: "октябрь", 11: "ноябрь", 12: "декабрь"
    }

    chart_df["m"] = chart_df[COL_DATE].dt.month
    chart_df["y"] = chart_df[COL_DATE].dt.year

    chart_df["label"] = chart_df["m"].map(months) + " " + chart_df["y"].astype(str)

    grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()


# ================= CHART =================

fig, ax = plt.subplots(figsize=(15, 5))

ax.bar(
    range(len(grouped)),
    grouped[COL_WEIGHT],
    width=0.75
)

ax.set_ylabel("Вес (кг)")
ax.set_xticks(range(len(grouped)))
ax.set_xticklabels(grouped["label"], rotation=90)

plt.tight_layout()

st.pyplot(fig)


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии",
    "📊 Все данные"
])


# ================= LIST =================

with tab1:

    table = df.copy()

    if COL_ATA:
        table["ATA_ext"] = table[COL_ATA].dt.strftime("%H:%M")

    table = table.sort_values(COL_DATE, ascending=False)

    table = table.reset_index(drop=True)

    table.insert(0, "№", range(1, len(table)+1))

    st.dataframe(table, use_container_width=True)


# ================= SPLIT =================

with tab2:

    if not COL_SPLIT:

        st.info("Нет колонки 'Дробление'")

    else:

        split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split_df.groupby(COL_AWB):

            if len(g) < 2:
                continue

            cartons = g[COL_CARTON].dropna().astype(int).tolist()

            rows.append({
                "AWB": awb,
                "Q-ty of flights": len(g),
                "Total No of cartons": sum(cartons),
                "Q-ty of separate cartons": ", ".join(map(str, cartons))
            })

        if not rows:

            st.info("Дробленных партий нет")

        else:

            split_table = pd.DataFrame(rows)

            split_table.insert(0, "№", range(1, len(split_table)+1))

            st.dataframe(split_table, use_container_width=True)


# ================= RAW =================

with tab3:

    st.dataframe(df, use_container_width=True)

