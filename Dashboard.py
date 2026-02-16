import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import numpy as np

# ========================================
# НАСТРОЙКА
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

.metric-box {
    background:#f1f5f9;
    padding:15px;
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

    # удалить unnamed колонки
    df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]

    df.columns = df.columns.str.strip()

    # безопасная конвертация дат
    for col in ["Outbound date","ETD","ETA","ATD","ATA"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # только 2026+
    df = df[df["Outbound date"] >= "2026-01-01"]

    df["Outbound weight (kg)"] = pd.to_numeric(
        df["Outbound weight (kg)"],
        errors="coerce"
    )

    df = df[df["Outbound weight (kg)"].notna()]

    return df.reset_index(drop=True)

df = load_data()

# ========================================
# KPI
# ========================================

kpi_df = df.copy()

kpi_df["Transit"] = (
    kpi_df["ATA"] - kpi_df["ATD"]
).dt.days

# убрать нереальные значения
kpi_df.loc[
    (kpi_df["Transit"] < 0) |
    (kpi_df["Transit"] > 15),
    "Transit"
] = np.nan

total_weight = int(kpi_df["Outbound weight (kg)"].sum())

total_flights = len(kpi_df)

avg_weight = int(kpi_df["Outbound weight (kg)"].mean())

avg_transit = int(kpi_df["Transit"].mean())

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

fig = px.bar(
    chart_df,
    x=chart_df.columns[0],
    y="Outbound weight (kg)",
    text="Outbound weight (kg)"
)

fig.update_traces(
    textposition="inside",
    textangle=0
)

fig.update_layout(height=500)

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

    # безопасная дата конвертация
    for col in ["Outbound date","ETD","ETA","ATD","ATA"]:
        table[col] = pd.to_datetime(
            table[col],
            errors="coerce"
        ).dt.date

    if "ATA_ext" in table.columns:
        table = table.rename(
            columns={"ATA_ext":"ATA_time"}
        )

    table.insert(
        0,
        "№",
        range(1,len(table)+1)
    )

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

            ata = g["ATA"].dt.date.astype(str).tolist()

            rows.append({

                "AWB":awb,

                "Кол-во рейсов":len(g),

                "Всего коробок":sum(cartons),

                "Раздельные коробки":", ".join(map(str,cartons)),

                "ATA (при дроблении)":", ".join(ata)

            })

        split_table=pd.DataFrame(rows)

        split_table.insert(
            0,
            "№",
            range(1,len(split_table)+1)
        )

        st.dataframe(
            split_table,
            use_container_width=True
        )
