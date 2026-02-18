import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="Свод по рейсам Китай-Узбекистан",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

START_ROW = 874


# =====================================
# LOAD DATA
# =====================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl"
    )

    df.columns = df.columns.astype(str).str.strip()

    df = df.iloc[START_ROW:].reset_index(drop=True)

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    return df


df = load_data()


# =====================================
# COLUMN FINDER
# =====================================

def find_col(names):

    for col in df.columns:

        c = col.lower()

        for name in names:

            if name in c:
                return col

    return None


COL_PROJECT = find_col(["проект"])
COL_WEIGHT = find_col(["weight"])
COL_DATE = find_col(["outbound date"])
COL_CARTON = find_col(["carton"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata.1"])
COL_SPLIT = find_col(["дроб"])
COL_REMARKS = find_col(["remark"])

COL_HUB_DATE = find_col(["хаб"])
COL_DAYS_TAS = find_col(["терминала tas"])
COL_DAYS_HUB = find_col(["до хаб"])


# =====================================
# CLEAN TYPES
# =====================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

DATE_COLS = [
    COL_DATE,
    COL_ETD,
    COL_ATD,
    COL_ETA,
    COL_ATA,
    COL_HUB_DATE
]

for c in DATE_COLS:

    if c:

        df[c] = pd.to_datetime(
            df[c],
            errors="coerce",
            dayfirst=True
        )


df = df.dropna(subset=[COL_DATE])


# =====================================
# FORMAT DATE FUNCTION
# =====================================

def fmt_date(series):

    return series.dt.strftime("%d-%m-%Y")


# =====================================
# HEADER
# =====================================

st.title("Свод по рейсам Китай-Узбекистан")


# =====================================
# FILTER PROJECT
# =====================================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

filtered = df.copy()

if project != "Все":

    filtered = filtered[filtered[COL_PROJECT] == project]


# =====================================
# KPI
# =====================================

total_weight = int(filtered[COL_WEIGHT].sum())

total_flights = len(filtered)

avg_weight = int(filtered[COL_WEIGHT].mean())


# transit = ATA - ATD (correct logic)

transit_series = (

    filtered[COL_ATA] - filtered[COL_ATD]

).dt.days


avg_transit = int(transit_series.mean())


c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")

c2.metric("Количество рейсов", total_flights)

c3.metric("Средний вес", f"{avg_weight} кг")

c4.metric("Среднее транзитное время", f"{avg_transit} дней")


# =====================================
# CHART TITLE
# =====================================

st.subheader("Перевезенные партии, кг")


# =====================================
# PERIOD SELECTOR
# =====================================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


chart = filtered.copy()

if period == "По дням":

    chart["grp"] = chart[COL_DATE].dt.strftime("%d-%m-%Y")

elif period == "По неделям":

    chart["grp"] = chart[COL_DATE].dt.to_period("W").astype(str)

else:

    chart["grp"] = chart[COL_DATE].dt.strftime("%m-%Y")


grouped = (

    chart.groupby("grp")[COL_WEIGHT]

    .sum()

    .reset_index()

)

grouped.columns = ["Дата", "Вес"]


# =====================================
# CHART
# =====================================

fig = px.bar(

    grouped,

    x="Дата",
    y="Вес",
    text="Вес"
)

fig.update_traces(

    textposition="outside",

    textangle=0,

    textfont_size=12
)

fig.update_layout(

    height=500,

    xaxis_tickangle=-45,

    uniformtext_minsize=10,

    uniformtext_mode="hide"
)

st.plotly_chart(

    fig,

    use_container_width=True
)


# =====================================
# TABS
# =====================================

tab1, tab2 = st.tabs(["Список партий", "Дробленные партии"])


# =====================================
# SEARCH BOX
# =====================================

search_awb = st.text_input(

    "Поиск по AWB номеру:",
    ""
)


# =====================================
# TABLE FORMATTER
# =====================================

def prepare_table(data):

    table = data.copy()

    if search_awb:

        table = table[
            table[COL_AWB].astype(str)
            .str.contains(search_awb, case=False, na=False)
        ]

    table.insert(0, "№", range(1, len(table) + 1))

    for c in DATE_COLS:

        if c in table.columns:

            table[c] = fmt_date(table[c])

    cols = [

        "№",

        COL_PROJECT,
        COL_CARTON,
        COL_WEIGHT,
        COL_DATE,
        COL_AWB,
        COL_FLIGHT,
        COL_VIA,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        COL_HUB_DATE,
        COL_DAYS_TAS,
        COL_DAYS_HUB,
        COL_REMARKS

    ]

    cols = [c for c in cols if c in table.columns]

    table = table[cols]

    rename = {

        COL_PROJECT: "Проект",
        COL_CARTON: "Outbound carton",
        COL_WEIGHT: "Outbound weight",
        COL_DATE: "Outbound date",
        COL_AWB: "Booking/AWB NO",
        COL_FLIGHT: "Flight No.",
        COL_VIA: "VIA",
        COL_ETD: "ETD",
        COL_ATD: "ATD",
        COL_ETA: "ETA",
        COL_ATA: "ATA",
        COL_HUB_DATE: "Поступление на склад ХАБ",
        COL_DAYS_TAS: "Дней до прибытия до TAS",
        COL_DAYS_HUB: "Дней до прибытия до ХАБ",
        COL_REMARKS: "Remarks"
    }

    return table.rename(columns=rename)


# =====================================
# TAB1
# =====================================

with tab1:

    table = prepare_table(filtered)

    st.dataframe(

        table,

        use_container_width=True,

        height=700
    )


# =====================================
# TAB2
# =====================================

with tab2:

    if COL_SPLIT:

        split = filtered[
            filtered[COL_SPLIT]
            .astype(str)
            .str.contains("да", case=False, na=False)
        ]

        table = prepare_table(split)

        st.dataframe(

            table,

            use_container_width=True,

            height=700
        )

    else:

        st.info("Нет дробленных партий")
