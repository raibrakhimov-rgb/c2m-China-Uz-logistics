import streamlit as st
import pandas as pd
import altair as alt
import requests
from io import StringIO
from datetime import timedelta

# ================== CONFIG ==================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
SHEET_NAME = "Logistics operations"

START_ROW = 863
HEADER_ROW = 2

# ================== MONTHS RU ==================

MONTHS_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

# ================== UI ==================

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)

st.title("📊 Сводная по вылетам из Материкового Китая в Узбекистан")

# ================== LOAD DATA ==================


@st.cache_data(ttl=600)
def load_data():

    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

    r = requests.get(url)
    r.encoding = "utf-8"

    df = pd.read_csv(StringIO(r.text))

    # Header
    headers = df.iloc[HEADER_ROW - 1]
    df.columns = headers

    # Data
    df = df.iloc[START_ROW - 1 :].copy()

    df = df.reset_index(drop=True)

    return df


df = load_data()

# ================== COLUMNS ==================

COL_WEIGHT = "Outbound weight (kg)"
COL_ETD = "ETD"
COL_ATD = "ATD"
COL_ETA = "ETA"
COL_ATA = "ATA"
COL_AWB = "Booking/AWB No"
COL_FLIGHT = "Flight No.:"
COL_COMMENT = "Комментарии"

# ================== CLEAN ==================

df = df[
    [
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        COL_WEIGHT,
        COL_COMMENT,
    ]
]

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    df[c] = pd.to_datetime(df[c], errors="coerce")

df = df.dropna(subset=[COL_ETD, COL_WEIGHT])

# ================== METRICS ==================

total_shipments = len(df)
total_weight = int(df[COL_WEIGHT].sum())

in_transit = df[COL_ATA].isna().sum()
delivered = total_shipments - in_transit

transit_days = (
    (df[COL_ATA] - df[COL_ETD])
    .dt.days
    .dropna()
    .mean()
)

sla = (
    (df[COL_ATA] <= df[COL_ETA])
    .mean()
    * 100
)

# ================== HEADER ==================

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", total_shipments)
c2.metric("⚖️ Вес (кг)", total_weight)
c3.metric("✈️ В пути", in_transit)
c4.metric("📦 Доставлено", delivered)
c5.metric("⏱ Транзит (дн)", round(transit_days, 1))
c6.metric("🎯 SLA %", round(sla, 1))

# ================== TABS ==================

tab1, tab2, tab3 = st.tabs(
    ["✈️ Вылеты", "⏰ Просрочки", "📋 Список партий"]
)

# =========================================================
# ================== TAB 1 : CHART ========================
# =========================================================

with tab1:

    st.subheader("✈️ Вылеты")

    mode = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True,
    )

    chart_df = df.copy()

    chart_df["date"] = chart_df[COL_ETD]

    # ================== GROUP ==================

    if mode == "По дням":

        grouped = (
            chart_df
            .groupby(chart_df["date"].dt.date)[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        grouped["label"] = grouped["date"].astype(str)

    elif mode == "По неделям":

        chart_df["week_start"] = (
            chart_df["date"]
            - pd.to_timedelta(chart_df["date"].dt.weekday, unit="D")
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

    else:

        chart_df["year"] = chart_df["date"].dt.year
        chart_df["month"] = chart_df["date"].dt.month

        grouped = (
            chart_df
            .groupby(["year", "month"])[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        grouped["label"] = (
            grouped["month"].map(MONTHS_RU)
            + " "
            + grouped["year"].astype(str)
        )

    grouped = grouped.sort_values(by=grouped.columns[0])

    # ================== CHART ==================

    bar_width = 40

    x_encoding = alt.X(
        "label:N",
        title="Период",
        sort=None,
        scale=alt.Scale(
            paddingInner=0,
            paddingOuter=0,
            rangeStep=bar_width,
        ),
    )

    chart = (
        alt.Chart(grouped)
        .mark_bar()
        .encode(
            x=x_encoding,
            y=alt.Y(
                f"{COL_WEIGHT}:Q",
                title="Вес (кг)"
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Период"),
                alt.Tooltip(f"{COL_WEIGHT}:Q", title="Вес (кг)"),
            ],
        )
        .properties(
            height=420
        )
    )

    st.altair_chart(chart, use_container_width=True)

# =========================================================
# ================== TAB 2 : DELAYS =======================
# =========================================================

with tab2:

    st.subheader("⏰ Просрочки > 1 дня")

    delay_df = df.copy()

    delay_df["Delay_Arrival_d"] = (
        (delay_df[COL_ATA] - delay_df[COL_ETA]).dt.days
    )

    delay_df["Delay_Departure_d"] = (
        (delay_df[COL_ATD] - delay_df[COL_ETD]).dt.days
    )

    delay_df = delay_df[
        delay_df["Delay_Arrival_d"] > 1
    ]

    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        delay_df[c] = delay_df[c].dt.strftime("%d.%m.%Y")

    delay_df = delay_df[
        [
            COL_AWB,
            COL_FLIGHT,
            COL_ETD,
            COL_ATD,
            COL_ETA,
            COL_ATA,
            "Delay_Departure_d",
            "Delay_Arrival_d",
            COL_COMMENT,
        ]
    ]

    st.dataframe(delay_df, use_container_width=True)

# =========================================================
# ================== TAB 3 : TABLE ========================
# =========================================================

with tab3:

    st.subheader("📋 Список партий")

    table_df = df.copy()

    table_df = table_df.sort_values(
        COL_ETD, ascending=False
    )

    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        table_df[c] = table_df[c].dt.strftime("%d.%m.%Y")

    table_df = table_df[
        [
            COL_AWB,
            COL_FLIGHT,
            COL_ETD,
            COL_ATD,
            COL_ETA,
            COL_ATA,
            COL_WEIGHT,
            COL_COMMENT,
        ]
    ]

    table_df = table_df.rename(
        columns={
            COL_AWB: "AWB",
            COL_FLIGHT: "Flight",
            COL_WEIGHT: "Weight (kg)",
            COL_COMMENT: "Comment",
        }
    )

    st.dataframe(table_df, use_container_width=True)
