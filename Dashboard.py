import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Сводная по вылетам Китай → Узбекистан",
    layout="wide"
)

st.title("✈️ Сводная по вылетам Китай → Узбекистан")

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# =====================================================
# LOAD DATA (HEADER ROW 1, DATA FROM ROW 875)
# =====================================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=0
    )

    # очистить названия колонок
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.replace("\n", " ")
    )

    # удалить unnamed колонки
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # взять данные начиная со строки 875
    df = df.iloc[874:].copy()

    df.reset_index(drop=True, inplace=True)

    return df


df = load_data()

# =====================================================
# AUTO FIND COLUMNS
# =====================================================

def find_col(keywords):

    for col in df.columns:

        name = col.lower()

        for k in keywords:

            if k in name:

                return col

    return None


COL_PROJECT = find_col(["project", "проект"])
COL_WEIGHT = find_col(["weight"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_AWB = find_col(["awb"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata"])
COL_SPLIT = find_col(["дроб", "split"])

# =====================================================
# VALIDATE
# =====================================================

if COL_WEIGHT is None or COL_DATE is None:

    st.error("Ошибка: не найдены колонки")
    st.write(df.columns.tolist())
    st.stop()

# =====================================================
# FORMAT TYPES
# =====================================================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:

    if c:

        df[c] = pd.to_datetime(df[c], errors="coerce")

df = df.dropna(subset=[COL_WEIGHT, COL_DATE])

# =====================================================
# PROJECT FILTER
# =====================================================

if COL_PROJECT:

    projects = ["Все"] + sorted(
        df[COL_PROJECT].dropna().unique()
    )

    selected_project = st.radio(
        "Проект",
        projects,
        horizontal=True
    )

    if selected_project != "Все":

        df = df[df[COL_PROJECT] == selected_project]

# =====================================================
# KPI
# =====================================================

total_weight = int(df[COL_WEIGHT].sum())

total_flights = (
    df[COL_AWB].nunique()
    if COL_AWB else len(df)
)

avg_weight = int(df[COL_WEIGHT].mean())

# transit time safe
avg_transit = None

if COL_ETD and COL_ATA:

    temp = df.dropna(subset=[COL_ETD, COL_ATA])

    temp["transit"] = (
        temp[COL_ATA] - temp[COL_ETD]
    ).dt.days

    temp = temp[
        (temp["transit"] >= 0) &
        (temp["transit"] <= 15)
    ]

    if len(temp):

        avg_transit = round(temp["transit"].mean(), 1)

# KPI DISPLAY

c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")

c2.metric("Количество рейсов", total_flights)

c3.metric("Средний вес", f"{avg_weight} кг")

c4.metric(
    "Средний transit time",
    f"{avg_transit} дней" if avg_transit else "-"
)

# =====================================================
# CHART PERIOD
# =====================================================

period = st.radio(
    "Период",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

if period == "По дням":

    chart_df = (
        chart_df.groupby(COL_DATE)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_DATE)
    )

elif period == "По неделям":

    chart_df["week"] = chart_df[COL_DATE].dt.to_period("W")

    chart_df = (
        chart_df.groupby("week")[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    chart_df[COL_DATE] = chart_df["week"].astype(str)

elif period == "По месяцам":

    chart_df["month"] = chart_df[COL_DATE].dt.to_period("M")

    chart_df = (
        chart_df.groupby("month")[COL_WEIGHT]
        .sum()
        .reset_index()
    )

    chart_df[COL_DATE] = chart_df["month"].astype(str)

# =====================================================
# CHART
# =====================================================

fig = px.bar(

    chart_df,

    x=COL_WEIGHT,

    y=COL_DATE,

    orientation="h",

    text=COL_WEIGHT,

    height=600
)

fig.update_traces(
    textposition="inside",
    textangle=0
)

fig.update_layout(
    yaxis_title="",
    xaxis_title="Вес (кг)"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABS
# =====================================================

tab1, tab2 = st.tabs([
    "Список партий",
    "Дробленные партии"
])

# =====================================================
# SHIPMENTS TABLE
# =====================================================

with tab1:

    table = df.copy()

    table.insert(
        0,
        "№",
        range(1, len(table)+1)
    )

    st.dataframe(
        table,
        use_container_width=True,
        height=600
    )

# =====================================================
# SPLIT SHIPMENTS
# =====================================================

with tab2:

    if COL_SPLIT:

        split = df[
            df[COL_SPLIT]
            .astype(str)
            .str.lower()
            .isin(["да", "yes"])
        ]

        if len(split):

            split.insert(
                0,
                "№",
                range(1, len(split)+1)
            )

            st.dataframe(
                split,
                use_container_width=True
            )

        else:

            st.info("Нет дробленных партий")

    else:

        st.info("Колонка дробления не найдена")
