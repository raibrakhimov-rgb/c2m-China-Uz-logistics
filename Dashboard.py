import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="Логистика Китай → Узбекистан",
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
        engine="openpyxl",
        header=0
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

        col_low = col.lower()

        for name in names:

            if name in col_low:
                return col

    return None


COL_PROJECT = find_col(["проект", "project"])
COL_WEIGHT = find_col(["outbound weight", "weight"])
COL_DATE = find_col(["outbound date", "date"])
COL_CARTON = find_col(["outbound carton", "carton"])
COL_AWB = find_col(["awb", "booking"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata.1"])
COL_SPLIT = find_col(["дроб"])
COL_REMARKS = find_col(["remark"])

COL_HUB_DATE = find_col(["поступление на склад хаб"])
COL_DAYS_TAS = find_col(["дней до прибытия из swe до терминала tas"])
COL_DAYS_HUB = find_col(["дней до прибытия из swe до хаб"])


CRITICAL = [
    COL_PROJECT,
    COL_WEIGHT,
    COL_DATE
]

if any(x is None for x in CRITICAL):

    st.error("Не найдены критические колонки")
    st.write(df.columns.tolist())
    st.stop()


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

    if c and c in df.columns:

        df[c] = pd.to_datetime(
            df[c],
            errors="coerce",
            dayfirst=True
        ).dt.date


df = df.dropna(subset=[COL_DATE])


# =====================================
# REMOVE UNUSED COLUMNS
# =====================================

DROP_NAMES = [
    "pod",
    "wh_ext",
    "ata_ext",
    "поступление на склад"
]

DROP_COLS = []

for col in df.columns:

    col_low = col.lower()

    for name in DROP_NAMES:

        if name in col_low and "хаб" not in col_low:

            DROP_COLS.append(col)

df = df.drop(columns=DROP_COLS, errors="ignore")


# =====================================
# ROUND TRANSIT DAYS
# =====================================

for c in [COL_DAYS_TAS, COL_DAYS_HUB]:

    if c and c in df.columns:

        df[c] = pd.to_numeric(
            df[c],
            errors="coerce"
        ).round(0).astype("Int64")


# =====================================
# HEADER
# =====================================

st.title("Логистика Китай → Узбекистан")


# =====================================
# FILTER PROJECT
# =====================================

projects = ["Все"] + sorted(
    df[COL_PROJECT].dropna().unique().tolist()
)

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

filtered = df.copy()

if project != "Все":

    filtered = filtered[
        filtered[COL_PROJECT] == project
    ]


# =====================================
# KPI
# =====================================

total_weight = int(filtered[COL_WEIGHT].sum())

total_flights = len(filtered)

avg_weight = int(filtered[COL_WEIGHT].mean()) if total_flights > 0 else 0


transit = None

if COL_ETD and COL_ATA:

    etd = pd.to_datetime(filtered[COL_ETD], errors="coerce")

    ata = pd.to_datetime(filtered[COL_ATA], errors="coerce")

    transit = (ata - etd).dt.days.dropna()


avg_transit = int(transit.mean()) if transit is not None and len(transit) > 0 else 0


c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")
c2.metric("Количество рейсов", total_flights)
c3.metric("Средний вес", f"{avg_weight} кг")
c4.metric("Средний transit time", f"{avg_transit} дней")


# =====================================
# PERIOD SELECTOR
# =====================================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


chart = filtered.copy()

chart[COL_DATE] = pd.to_datetime(chart[COL_DATE], errors="coerce")

if period == "По дням":

    grouped = (
        chart.groupby(chart[COL_DATE].dt.date)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

elif period == "По неделям":

    grouped = (
        chart.groupby(chart[COL_DATE].dt.to_period("W"))[COL_WEIGHT]
        .sum()
        .reset_index()
    )

else:

    grouped = (
        chart.groupby(chart[COL_DATE].dt.to_period("M"))[COL_WEIGHT]
        .sum()
        .reset_index()
    )


grouped.columns = ["Дата", "Вес"]

grouped["Дата"] = grouped["Дата"].astype(str)


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

    textposition="inside"
)

fig.update_layout(

    height=500
)

st.plotly_chart(

    fig,
    use_container_width=True
)


# =====================================
# TABS
# =====================================

tab1, tab2 = st.tabs(

    ["Список партий", "Дробленные партии"]
)


# =====================================
# FINAL COLUMN ORDER
# =====================================

FINAL_COLUMNS = [

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


RENAME_MAP = {

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
    COL_DAYS_TAS: "Дней до прибытия из SWE до Терминала TAS",
    COL_DAYS_HUB: "Дней до прибытия из SWE до ХАБа",
    COL_REMARKS: "Remarks"
}


# =====================================
# SHIPMENTS TABLE
# =====================================

with tab1:

    table = filtered.copy()

    if "№" in table.columns:

        table = table.drop(columns=["№"])

    table.insert(

        0,
        "№",
        range(1, len(table) + 1)
    )

    cols = [c for c in FINAL_COLUMNS if c in table.columns]

    table = table[cols]

    table = table.rename(columns=RENAME_MAP)

    st.dataframe(

        table,
        use_container_width=True,
        height=700
    )


# =====================================
# SPLIT SHIPMENTS
# =====================================

with tab2:

    if COL_SPLIT is None:

        st.info("Нет колонки дробления")

    else:

        split = filtered[
            filtered[COL_SPLIT]
            .astype(str)
            .str.lower()
            .str.contains("да")
        ]

        if "№" in split.columns:

            split = split.drop(columns=["№"])

        split.insert(

            0,
            "№",
            range(1, len(split) + 1)
        )

        cols = [c for c in FINAL_COLUMNS if c in split.columns]

        split = split[cols]

        split = split.rename(columns=RENAME_MAP)

        st.dataframe(

            split,
            use_container_width=True,
            height=700
        )
