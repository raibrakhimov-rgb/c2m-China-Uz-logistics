import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.graph_objects as go
from datetime import datetime

# ===============================
# НАСТРОЙКИ СТРАНИЦЫ
# ===============================

st.set_page_config(
    page_title="Логистика Китай → Узбекистан",
    layout="wide"
)

# стиль
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
}
.metric-card {
    background: #f8fafc;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# GOOGLE SHEETS
# ===============================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ===============================
# ЗАГРУЗКА
# ===============================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    # удалить пустые
    df = df.dropna(how="all")

    # удалить unnamed
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    # trim
    df.columns = df.columns.astype(str).str.strip()

    # фильтр только с 2026
    df["Outbound date"] = pd.to_datetime(df["Outbound date"], errors="coerce")

    df = df[df["Outbound date"] >= "2026-01-01"]

    df = df.reset_index(drop=True)

    return df


df = load_data()

# ===============================
# НОРМАЛИЗАЦИЯ
# ===============================

df["Outbound weight (kg)"] = pd.to_numeric(df["Outbound weight (kg)"], errors="coerce")

date_cols = ["ETD", "ETA", "ATD", "ATA"]

for col in date_cols:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

# transit time
if "ATA" in df.columns and "ATD" in df.columns:
    df["Transit"] = (
        pd.to_datetime(df["ATA"]) - pd.to_datetime(df["ATD"])
    ).dt.days

# ===============================
# KPI
# ===============================

total_weight = int(df["Outbound weight (kg)"].sum())

total_flights = df["Flight No.:"].nunique()

avg_weight = int(df["Outbound weight (kg)"].mean())

avg_transit = int(df["Transit"].dropna().mean())

st.title("✈️ Логистика Китай → Узбекистан")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Общий вес", f"{total_weight:,} кг")
c2.metric("Количество рейсов", total_flights)
c3.metric("Средний вес", f"{avg_weight:,} кг")
c4.metric("Средний transit time", f"{avg_transit} дней")

# ===============================
# ГРАФИК
# ===============================

st.subheader("Объемы отправок")

group = st.radio(
    "",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

if group == "По дням":

    grouped = (
        chart_df.groupby("Outbound date")["Outbound weight (kg)"]
        .sum()
        .reset_index()
        .sort_values("Outbound date")
    )

    grouped["label"] = grouped["Outbound date"].astype(str)

elif group == "По неделям":

    chart_df["week"] = chart_df["Outbound date"].apply(
        lambda x: x - pd.Timedelta(days=x.weekday())
    )

    grouped = (
        chart_df.groupby("week")["Outbound weight (kg)"]
        .sum()
        .reset_index()
        .sort_values("week")
    )

    grouped["label"] = grouped["week"].astype(str)

else:

    chart_df["month"] = chart_df["Outbound date"].dt.to_period("M")

    grouped = (
        chart_df.groupby("month")["Outbound weight (kg)"]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    grouped["label"] = grouped["month"].astype(str)

# plotly chart

fig = go.Figure()

fig.add_trace(go.Bar(

    x=grouped["label"],
    y=grouped["Outbound weight (kg)"],

    text=grouped["Outbound weight (kg)"].astype(int).astype(str) + " кг",

    textposition="inside",

    textangle=0,

))

fig.update_layout(

    height=500,

    plot_bgcolor="white",

    paper_bgcolor="white",

    xaxis_title="Дата",

    yaxis_title="Вес (кг)",

)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# ВКЛАДКИ
# ===============================

tab1, tab2 = st.tabs(["Список партий", "Дробленные партии"])

# ===============================
# СПИСОК ПАРТИЙ
# ===============================

with tab1:

    table = df.copy()

    # удалить ненужные
    drop_cols = [
        "Batch No.",
        "ATA.1",
        "wh_ext",
        "POD",
        "Комментарий"
    ]

    for col in drop_cols:
        if col in table.columns:
            table = table.drop(columns=col)

    # удалить unnamed индекс
    table = table.reset_index(drop=True)

    # добавить номер
    if "№" in table.columns:
        table = table.drop(columns="№")

    table.insert(0, "№", table.index + 1)

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

# ===============================
# SPLIT SHIPMENTS
# ===============================

with tab2:

    if "Дробление" in df.columns:

        split = df[df["Дробление"] == "Да"]

        result = []

        for awb, g in split.groupby("Booking/AWB NO"):

            cartons = g["Outbound carton"].tolist()

            result.append({

                "AWB": awb,

                "Количество рейсов": len(g),

                "Коробок всего": sum(cartons),

                "Коробки": ", ".join(map(str, cartons)),

                "ATA (при дроблении)": g["ATA"].astype(str).iloc[-1]

            })

        split_df = pd.DataFrame(result)

        split_df.insert(0, "№", split_df.index + 1)

        st.dataframe(
            split_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Нет дробленных партий")
