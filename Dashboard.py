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

START_ROW = 874  # брать данные с 875 строки


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
COL_WEIGHT = find_col(["weight"])
COL_DATE = find_col(["outbound date", "date"])
COL_CARTON = find_col(["carton"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_VIA = find_col(["via"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_SPLIT = find_col(["дроб"])


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

df[COL_DATE] = pd.to_datetime(
    df[COL_DATE],
    errors="coerce",
    dayfirst=True
)

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:

    if c:
        df[c] = pd.to_datetime(
            df[c],
            errors="coerce",
            dayfirst=True
        )

df = df.dropna(subset=[COL_DATE])


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

avg_weight = int(filtered[COL_WEIGHT].mean())

transit = None

if COL_ETD and COL_ATA:

    transit = (
        filtered[COL_ATA] - filtered[COL_ETD]
    ).dt.days

    transit = transit.dropna()

avg_transit = int(transit.mean()) if transit is not None and len(transit)>0 else 0


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

if period == "По дням":

    grouped = (
        chart.groupby(chart[COL_DATE].dt.date)[COL_WEIGHT]
        .sum()
        .reset_index()
    )

elif period == "По неделям":

    grouped = (
        chart.groupby(
            chart[COL_DATE].dt.to_period("W")
        )[COL_WEIGHT]
        .sum()
        .reset_index()
    )

else:

    grouped = (
        chart.groupby(
            chart[COL_DATE].dt.to_period("M")
        )[COL_WEIGHT]
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
    textposition="inside",
    textangle=0
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
# SHIPMENTS TABLE
# =====================================

with tab1:

    table = filtered.copy()

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(
        0,
        "№",
        range(1, len(table)+1)
    )

    st.dataframe(
        table,
        use_container_width=True
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
            range(1, len(split)+1)
        )

        st.dataframe(
            split,
            use_container_width=True
        )
