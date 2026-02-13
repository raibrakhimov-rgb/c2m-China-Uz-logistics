import streamlit as st
import pandas as pd
import altair as alt
import calendar


# ============================
# CONFIG
# ============================

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)


SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"


START_ROW = 862   # с какой строки тянуть (863 → индекс 862)


# ============================
# LOAD DATA
# ============================

@st.cache_data(ttl=600)
def load_data():

    df = pd.read_csv(SHEET_URL)

    df = df.iloc[START_ROW:].reset_index(drop=True)

    df = df.dropna(how="all")

    return df


df = load_data()


# ============================
# COLUMN MAP
# ============================

COL_WEIGHT = "Outbound weight (kg)"
COL_ETD = "ETD"
COL_ETA = "ETA"
COL_ATD = "ATD"
COL_ATA = "ATA"
COL_ATA_EXT = "ATA_ext"
COL_AWB = "Booking/AWB NO"
COL_FLIGHT = "Flight No.:"
COL_COMMENT = "Комментарии"


# ============================
# PREPARE DATA
# ============================

DATE_COLS = [COL_ETD, COL_ETA, COL_ATD, COL_ATA]

for col in DATE_COLS:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")


df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")


df = df[df[COL_ETD].dt.year == 2026]


# ============================
# KPI
# ============================

total_batches = len(df)

total_weight = int(df[COL_WEIGHT].sum())

in_transit = df[df[COL_ATA].isna()].shape[0]

delivered = df[df[COL_ATA].notna()].shape[0]


# ============================
# HEADER
# ============================

st.title("📊 Сводная по вылетам из Материкового Китая в Узбекистан")


k1, k2, k3, k4 = st.columns(4)

k1.metric("📦 Партии", total_batches)
k2.metric("⚖️ Вес (кг)", total_weight)
k3.metric("✈️ В пути", in_transit)
k4.metric("🏢 Доставлено", delivered)


# ============================
# TABS
# ============================

tab1, tab2, tab3 = st.tabs([
    "✈️ Вылеты",
    "⏱ Просрочки",
    "📋 Список партий"
])


# =====================================================
# TAB 1 — CHART
# =====================================================

with tab1:

    st.subheader("✈️ Вылеты")


    view = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True
    )


    base = df[[COL_ETD, COL_WEIGHT]].dropna().copy()
    base = base.sort_values(COL_ETD)


    # ---------------- DAYS ----------------

    if view == "По дням":

        chart_df = (
            base
            .groupby(base[COL_ETD].dt.date)[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        chart_df.columns = ["date", "weight"]

        chart_df["date"] = pd.to_datetime(chart_df["date"])
        chart_df["label"] = chart_df["date"].dt.strftime("%d.%m")


        x_encoding = alt.X(
            "date:T",
            title="Дата",
            axis=alt.Axis(format="%d.%m", labelAngle=-45)
        )


    # ---------------- WEEKS ----------------

    elif view == "По неделям":

        base["week_start"] = base[COL_ETD].dt.to_period("W-MON").dt.start_time
        base["week_end"] = base["week_start"] + pd.Timedelta(days=6)

        chart_df = (
            base
            .groupby(["week_start", "week_end"])[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        chart_df["label"] = (
            chart_df["week_start"].dt.strftime("%d.%m")
            + "–"
            + chart_df["week_end"].dt.strftime("%d.%m")
        )

        chart_df["date"] = chart_df["label"]

        chart_df = chart_df[["date", "label", COL_WEIGHT]]
        chart_df.columns = ["date", "label", "weight"]


        x_encoding = alt.X(
            "date:N",
            title="Период",
            sort=None,
            scale=alt.Scale(paddingInner=0, paddingOuter=0)
        )


    # ---------------- MONTHS ----------------

    else:

        base["month"] = base[COL_ETD].dt.to_period("M")

        chart_df = (
            base
            .groupby("month")[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        chart_df["start"] = chart_df["month"].dt.start_time

        chart_df["label"] = (
            chart_df["start"].dt.month.apply(lambda x: calendar.month_name[x])
            + " "
            + chart_df["start"].dt.year.astype(str)
        )

        chart_df["date"] = chart_df["label"]

        chart_df = chart_df[["date", "label", COL_WEIGHT, "start"]]
        chart_df.columns = ["date", "label", "weight", "start"]

        chart_df = chart_df.sort_values("start")


        x_encoding = alt.X(
            "date:N",
            title="Период",
            sort=None,
            scale=alt.Scale(paddingInner=0, paddingOuter=0)
        )


    chart_df = chart_df.reset_index(drop=True)


    # ---------------- CHART ----------------

    chart = (
        alt.Chart(chart_df)
        .mark_bar(size=22)
        .encode(

            x=x_encoding,

            y=alt.Y(
                "weight:Q",
                title="Вес (кг)"
            ),

            tooltip=[
                alt.Tooltip("label:N", title="Период"),
                alt.Tooltip("weight:Q", title="Вес (кг)")
            ]
        )
        .properties(height=420)
    )


    st.altair_chart(chart, use_container_width=True)


# =====================================================
# TAB 2 — DELAYS
# =====================================================

with tab2:

    st.subheader("⏱ Просрочки > 1 дня")


    delay_df = df.copy()

    delay_df["Delay_Arrival_d"] = (
        (delay_df[COL_ATA] - delay_df[COL_ETA]).dt.days
    )

    delay_df["Delay_Departure_d"] = (
        (delay_df[COL_ATD] - delay_df[COL_ETD]).dt.days
    )


    delay_df = delay_df[delay_df["Delay_Arrival_d"] > 0]


    show_cols = [
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ETA,
        COL_ATD,
        COL_ATA,
        "Delay_Departure_d",
        "Delay_Arrival_d",
        COL_COMMENT
    ]


    delay_df = delay_df[show_cols]


    for c in DATE_COLS:
        delay_df[c] = delay_df[c].dt.strftime("%d.%m.%Y")


    st.dataframe(
        delay_df,
        use_container_width=True,
        hide_index=True
    )


# =====================================================
# TAB 3 — TABLE
# =====================================================

with tab3:

    st.subheader("📋 Список партий")


    table = df.copy()


    table["ETD"] = table[COL_ETD].dt.strftime("%d.%m.%Y")
    table["ATD"] = table[COL_ATD].dt.strftime("%d.%m.%Y")
    table["ETA"] = table[COL_ETA].dt.strftime("%d.%m.%Y")
    table["ATA"] = table[COL_ATA].dt.strftime("%d.%m.%Y")

    table["ATA_ext"] = pd.to_datetime(
        table[COL_ATA_EXT],
        errors="coerce"
    ).dt.strftime("%H:%M")


    table = table.sort_values(COL_ETD, ascending=False)


    table = table.rename(columns={
        COL_AWB: "AWB",
        COL_FLIGHT: "Flight",
        COL_WEIGHT: "Weight (kg)",
        COL_COMMENT: "Comment"
    })


    final_cols = [
        "AWB",
        "Flight",
        "ETD",
        "ATD",
        "ETA",
        "ATA",
        "ATA_ext",
        "Weight (kg)",
        "Comment"
    ]


    table = table[final_cols]


    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )
