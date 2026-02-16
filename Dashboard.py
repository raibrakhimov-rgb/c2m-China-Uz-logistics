import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import numpy as np

# ========================================
# НАСТРОЙКА СТРАНИЦЫ
# ========================================

st.set_page_config(
    page_title="Вылеты Китай → Узбекистан",
    layout="wide"
)

# ========================================
# СТИЛЬ
# ========================================

st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: Arial;
}

.kpi {
    background-color:#f8fafc;
    padding:20px;
    border-radius:10px;
}

</style>
""", unsafe_allow_html=True)

# ========================================
# GOOGLE SHEETS
# ========================================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ========================================
# ЗАГРУЗКА ДАННЫХ
# ========================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    df = pd.read_excel(BytesIO(r.content), header=1)

    # удалить пустые колонки
    df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]

    df.columns = df.columns.str.strip()

    # оставить только 2026+
    df["Outbound date"] = pd.to_datetime(df["Outbound date"], errors="coerce")

    df = df[df["Outbound date"] >= "2026-01-01"]

    # удалить строки без веса
    df["Outbound weight (kg)"] = pd.to_numeric(
        df["Outbound weight (kg)"],
        errors="coerce"
    )

    df = df[df["Outbound weight (kg)"].notna()]

    return df.reset_index(drop=True)

df = load_data()

# ========================================
# KPI (ПРАВИЛЬНЫЕ)
# ========================================

valid_df = df[
    df["Flight No.:"].notna() &
    df["Outbound weight (kg)"].notna()
].copy()

valid_df["ATD"] = pd.to_datetime(valid_df["ATD"], errors="coerce")
valid_df["ATA"] = pd.to_datetime(valid_df["ATA"], errors="coerce")

valid_df["Transit"] = (
    valid_df["ATA"] - valid_df["ATD"]
).dt.days

valid_df.loc[
    (valid_df["Transit"] < 0) |
    (valid_df["Transit"] > 15),
    "Transit"
] = np.nan

total_weight = int(valid_df["Outbound weight (kg)"].sum())

total_flights = valid_df.shape[0]

avg_weight = int(valid_df["Outbound weight (kg)"].mean())

avg_transit = int(valid_df["Transit"].mean())

# ========================================
# HEADER
# ========================================

st.title("✈️ Вылеты Китай → Узбекистан")

c1,c2,c3,c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")
c2.metric("Количество рейсов", total_flights)
c3.metric("Средний вес", f"{avg_weight} кг")
c4.metric("Средний transit time", f"{avg_transit} дней")

st.divider()

# ========================================
# ФИЛЬТР
# ========================================

projects = ["Все"] + sorted(df["Проект"].dropna().unique())

project = st.radio(
    "Проект",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df["Проект"] == project]

# ========================================
# ГРАФИК
# ========================================

period = st.radio(
    "Период",
    ["По дням","По неделям","По месяцам"],
    horizontal=True
)

chart_df = df.copy()

if period == "По дням":

    chart_df = chart_df.groupby(
        chart_df["Outbound date"].dt.date
    )["Outbound weight (kg)"].sum().reset_index()

    chart_df = chart_df.sort_values("Outbound date")

elif period == "По неделям":

    chart_df["week"] = chart_df["Outbound date"].dt.to_period("W")

    chart_df = chart_df.groupby("week")[
        "Outbound weight (kg)"
    ].sum().reset_index()

    chart_df["week"] = chart_df["week"].astype(str)

elif period == "По месяцам":

    chart_df["month"] = chart_df["Outbound date"].dt.to_period("M")

    chart_df = chart_df.groupby("month")[
        "Outbound weight (kg)"
    ].sum().reset_index()

    chart_df["month"] = chart_df["month"].astype(str)

# plotly chart
fig = px.bar(
    chart_df,
    x=chart_df.columns[0],
    y="Outbound weight (kg)",
    text="Outbound weight (kg)"
)

fig.update_traces(
    textposition="inside",
    textfont_size=14,
    textangle=0
)

fig.update_layout(
    height=500,
    xaxis_title="Дата",
    yaxis_title="Вес (кг)"
)

st.plotly_chart(fig, use_container_width=True)

# ========================================
# ВКЛАДКИ
# ========================================

tab1, tab2 = st.tabs([
    "Список партий",
    "Дробленные партии"
])

# ========================================
# СПИСОК ПАРТИЙ
# ========================================

with tab1:

    table = df.copy()

    table["Outbound date"] = table["Outbound date"].dt.date

    table["ATD"] = pd.to_datetime(table["ATD"]).dt.date
    table["ETA"] = pd.to_datetime(table["ETA"]).dt.date
    table["ETD"] = pd.to_datetime(table["ETD"]).dt.date
    table["ATA"] = pd.to_datetime(table["ATA"]).dt.date

    table = table.rename(columns={
        "ATA_ext":"ATA_time"
    })

    table.insert(0,"№", range(1,len(table)+1))

    search = st.text_input("Поиск")

    if search:
        table = table.astype(str).apply(
            lambda x: x.str.contains(search, case=False)
        ).any(axis=1)

    st.dataframe(
        table,
        use_container_width=True,
        height=600
    )

# ========================================
# SPLIT SHIPMENTS
# ========================================

with tab2:

    if "Дробление" not in df.columns:
        st.info("Нет данных")
    else:

        split_df = df[
            df["Дробление"].astype(str).str.lower()=="да"
        ]

        rows=[]

        for awb, g in split_df.groupby("Booking/AWB NO"):

            cartons = g["Outbound carton"].tolist()

            rows.append({

                "AWB":awb,

                "Кол-во рейсов":len(g),

                "Всего коробок":sum(cartons),

                "Раздельные коробки":", ".join(map(str,cartons)),

                "ATA (при дроблении)":
                ", ".join(
                    g["ATA"].astype(str)
                )

            })

        split_table=pd.DataFrame(rows)

        split_table.insert(0,"№", range(1,len(split_table)+1))

        st.dataframe(
            split_table,
            use_container_width=True
        )
