# ================= IMPORTS =================

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta


# ================= CONFIG =================

st.set_page_config(
    page_title="Logistics Dashboard",
    layout="wide"
)

SHEET_URL = "PASTE_YOUR_XLSX_EXPORT_LINK_HERE"


# ================= LOAD DATA =================

@st.cache_data
def load_data():
    df = pd.read_excel(SHEET_URL)
    df.columns = df.columns.str.strip()
    return df


df = load_data()


# ================= FIND COLUMNS =================

def find_col(keywords):
    for col in df.columns:
        name = col.lower()
        for k in keywords:
            if k in name:
                return col
    return None


COL_DATE = find_col(["outbound date", "date"])
COL_ETD = find_col(["etd"])
COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_AWB = find_col(["awb"])
COL_SPLIT = find_col(["дроб"])
COL_PROJECT = find_col(["проект"])
COL_COMMENT = find_col(["коммент"])


REQUIRED = [
    COL_DATE,
    COL_WEIGHT,
    COL_CARTON,
    COL_AWB,
    COL_PROJECT
]

if None in REQUIRED:
    st.error("❌ Не найдены обязательные колонки")
    st.write(df.columns.tolist())
    st.stop()


# ================= PREPARE DATA =================

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")
df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

df = df.dropna(subset=[COL_DATE])


# ================= PROJECT FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique().tolist())

project = st.radio(
    "Проект",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]


# ================= GROUP MODE =================

group_mode = st.radio(
    "",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


# ================= GROUPING =================

chart_df = df.copy()


# ---- BY DAY ----
if group_mode == "По дням":

    grouped = (
        chart_df
        .groupby(chart_df[COL_DATE].dt.date)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped["label"] = grouped[COL_DATE].apply(
        lambda x: x.strftime("%d.%m")
    )


# ---- BY WEEK ----
elif group_mode == "По неделям":

    chart_df["week_start"] = chart_df[COL_DATE] - pd.to_timedelta(
        chart_df[COL_DATE].dt.weekday, unit="d"
    )

    grouped = (
        chart_df
        .groupby("week_start")[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    grouped["week_end"] = grouped["week_start"] + timedelta(days=6)

    grouped["label"] = (
        grouped["week_start"].dt.strftime("%d.%m")
        + "-"
        + grouped["week_end"].dt.strftime("%d.%m")
    )


# ---- BY MONTH ----
else:

    chart_df["month"] = chart_df[COL_DATE].dt.to_period("M")

    grouped = (
        chart_df
        .groupby("month")[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    MONTHS_RU = {
        1: "январь", 2: "февраль", 3: "март",
        4: "апрель", 5: "май", 6: "июнь",
        7: "июль", 8: "август", 9: "сентябрь",
        10: "октябрь", 11: "ноябрь", 12: "декабрь"
    }

    grouped["label"] = grouped["month"].apply(
        lambda x: f"{MONTHS_RU[x.month]} {x.year}"
    )


grouped = grouped.sort_values(grouped.columns[0])


# ================= CHART =================

fig = px.bar(
    grouped,
    x="label",
    y=COL_WEIGHT,
    labels={
        "label": "",
        COL_WEIGHT: "Вес (кг)"
    }
)

# bar spacing
fig.update_layout(
    bargap=0.15,
    height=420
)

st.plotly_chart(fig, use_container_width=True)


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии",
    "📊 Данные"
])


# ================= BATCH LIST =================

with tab1:

    table = df.copy()

    table = table.sort_values(COL_DATE, ascending=False)

    table = table.reset_index(drop=True)
    table.index = table.index + 1

    st.dataframe(
        table,
        use_container_width=True
    )


# ================= SPLIT SHIPMENTS =================

with tab2:

    if COL_SPLIT is None:

        st.info("Колонка 'Дробление' не найдена")

    else:

        split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        groups = []

        for awb, g in split_df.groupby(COL_AWB):

            cartons = g[COL_CARTON].tolist()

            groups.append({
                "Booking/AWB NO": awb,
                "Q-ty of flights": len(g),
                "Total No of cartons": sum(cartons),
                "Q-ty of separate cartons": ", ".join(
                    map(str, cartons)
                )
            })


        split_table = pd.DataFrame(groups)

        if not split_table.empty:

            split_table.index = range(1, len(split_table)+1)
            split_table.insert(0, "№", split_table.index)

            st.dataframe(
                split_table,
                use_container_width=True
            )

        else:
            st.info("Нет дробленных партий")


# ================= RAW DATA =================

with tab3:

    st.dataframe(df, use_container_width=True)
