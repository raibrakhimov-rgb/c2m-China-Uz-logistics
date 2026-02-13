import streamlit as st
import pandas as pd
import altair as alt


# ================= CONFIG =================

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"

SLA_LIMIT = 1  # допустимая задержка (дни)


# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():

    df = pd.read_csv(SHEET_URL, header=1)

    # Данные с 863 строки
    df = df.iloc[862:].copy()

    return df


df = load_data()

st.set_page_config(layout="wide")

st.title("✈️ Сводная по вылетам из Материкового Китая в Узбекистан")

if df.empty:
    st.stop()


# ================= CLEAN =================

df.columns = df.columns.str.strip()


# Убираем колонку индексов
if df.columns[0].startswith("Unnamed"):
    df = df.drop(columns=[df.columns[0]])


def find_col(keys):

    for col in df.columns:
        for k in keys:
            if k.lower() in col.lower():
                return col

    return None


COL_WEIGHT = find_col(["weight", "kg", "вес"])
COL_FLIGHT = find_col(["flight"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_ATA_EXT = find_col(["ata_ext"])
COL_AWB = find_col(["awb", "booking"])
COL_COMMENT = find_col(["comment", "коммент"])


# ================= DATE PARSE =================

def parse(col):

    if not col:
        return None

    return pd.to_datetime(
        df[col],
        errors="coerce",
        dayfirst=True
    )


for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:

    if c:
        df[c] = parse(c)


# ================= CLEAN WEIGHT =================

if COL_WEIGHT:

    df[COL_WEIGHT] = (
        df[COL_WEIGHT]
        .astype(str)
        .str.replace(r"[^\d\.]", "", regex=True)
    )

    df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")


# ================= FILTER 2026 =================

if COL_ETD:

    df = df[
        (df[COL_ETD] >= "2026-01-01") &
        (df[COL_ETD] <= "2026-12-31")
    ]


# ================= STATUS =================

def get_status(row):

    if COL_ATA and pd.notna(row[COL_ATA]):
        return "Delivered"

    if COL_ATD and pd.notna(row[COL_ATD]):
        return "In Transit"

    if COL_ETD and pd.notna(row[COL_ETD]):
        return "Scheduled"

    return "Pending"


df["Status"] = df.apply(get_status, axis=1)


# ================= DELAYS =================

# Arrival delay (days)
if COL_ETA and COL_ATA:

    df["Delay_Arrival_d"] = (
        (df[COL_ATA] - df[COL_ETA])
        .dt.total_seconds() / 86400
    )


# Departure delay (days)
if COL_ETD and COL_ATD:

    df["Delay_Departure_d"] = (
        (df[COL_ATD] - df[COL_ETD])
        .dt.total_seconds() / 86400
    )


# ================= TRANSIT =================

if COL_ATD and COL_ATA:

    df["Transit_days"] = (
        (df[COL_ATA] - df[COL_ATD])
        .dt.total_seconds() / 86400
    )


# ================= SLA =================

if "Delay_Arrival_d" in df.columns:

    df["SLA_OK"] = df["Delay_Arrival_d"] <= SLA_LIMIT


# ================= FORMAT =================

def fmt(col):

    if col and col in df.columns:
        return df[col].dt.strftime("%d.%m.%Y")

    return None


ETD_FMT = fmt(COL_ETD)
ATD_FMT = fmt(COL_ATD)
ETA_FMT = fmt(COL_ETA)
ATA_FMT = fmt(COL_ATA)


if COL_ATA_EXT:

    df[COL_ATA_EXT] = pd.to_datetime(
        df[COL_ATA_EXT],
        errors="coerce"
    ).dt.strftime("%H:%M")


# ================= KPI =================

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", len(df))

c2.metric(
    "⚖️ Вес (кг)",
    int(df[COL_WEIGHT].sum()) if COL_WEIGHT else 0
)

c3.metric("✈️ В пути", len(df[df["Status"] == "In Transit"]))
c4.metric("🏭 Доставлено", len(df[df["Status"] == "Delivered"]))

c5.metric(
    "⏱ Транзит (дн)",
    round(df["Transit_days"].mean(), 2)
    if "Transit_days" in df.columns else "-"
)

c6.metric(
    "🎯 SLA %",
    round(df["SLA_OK"].mean() * 100, 1)
    if "SLA_OK" in df.columns else "-"
)


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "📊 Вылеты",
    "⏰ Просрочки",
    "📋 Список партий"
])


# ================= TAB 1 =================

import altair as alt
import calendar


with tab1:

    st.subheader("✈️ Вылеты")


    view = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True
    )


    if COL_ETD and COL_WEIGHT:

        base = df[[COL_ETD, COL_WEIGHT]].dropna().copy()
        base = base.sort_values(COL_ETD)


        # =============================
        # GROUPING
        # =============================


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



        elif view == "По неделям":

            base["week_start"] = base[COL_ETD].dt.to_period("W-MON").dt.start_time
            base["week_end"] = base["week_start"] + pd.Timedelta(days=6)

            chart_df = (
                base
                .groupby(["week_start", "week_end"])[COL_WEIGHT]
                .sum()
                .reset_index()
            )

            chart_df["date"] = chart_df["week_start"]

            chart_df["label"] = (
                chart_df["week_start"].dt.strftime("%d.%m")
                + "–"
                + chart_df["week_end"].dt.strftime("%d.%m")
            )

            chart_df = chart_df[["date", "label", COL_WEIGHT]]
            chart_df.columns = ["date", "label", "weight"]



        else:  # По месяцам

            base["month"] = base[COL_ETD].dt.to_period("M")

            chart_df = (
                base
                .groupby("month")[COL_WEIGHT]
                .sum()
                .reset_index()
            )

            chart_df["date"] = chart_df["month"].dt.start_time

            chart_df["label"] = (
                chart_df["date"].dt.month.apply(lambda x: calendar.month_name[x])
                + " "
                + chart_df["date"].dt.year.astype(str)
            )

            chart_df = chart_df[["date", "label", COL_WEIGHT]]
            chart_df.columns = ["date", "label", "weight"]


        chart_df = chart_df.sort_values("date")



        # =============================
        # CHART
        # =============================


        chart = (
            alt.Chart(chart_df)
            .mark_bar(size=18)
            .encode(
                x=alt.X(
                    "date:T",
                    title="Дата",
                    axis=alt.Axis(
                        labelAngle=-45,
                        format="%d.%m"
                    )
                ),

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


# ================= TAB 2 =================

with tab2:

    st.subheader("Просрочки > 1 дня")

    if "Delay_Arrival_d" in df.columns:

        delay = df[df["Delay_Arrival_d"] > SLA_LIMIT]


        table = pd.DataFrame()

        table["AWB"] = df[COL_AWB]
        table["Flight"] = df[COL_FLIGHT]

        table["ETD"] = ETD_FMT
        table["ATD"] = ATD_FMT
        table["ETA"] = ETA_FMT
        table["ATA"] = ATA_FMT

        table["Delay Arrival (d)"] = df["Delay_Arrival_d"].round(1)
        table["Delay Departure (d)"] = df["Delay_Departure_d"].round(1)

        table["Comment"] = df[COL_COMMENT]


        table = table.loc[delay.index]

        table = table.reset_index(drop=True)


        st.dataframe(table, use_container_width=True)


# ================= TAB 3 =================

with tab3:

    st.subheader("Список партий")


    table = pd.DataFrame()

    table["AWB"] = df[COL_AWB]
    table["Flight"] = df[COL_FLIGHT]

    table["ETD"] = ETD_FMT
    table["ATD"] = ATD_FMT
    table["ETA"] = ETA_FMT
    table["ATA"] = ATA_FMT

    if COL_ATA_EXT:
        table["ATA_ext"] = df[COL_ATA_EXT]

    table["Weight (kg)"] = df[COL_WEIGHT]
    table["Status"] = df["Status"]
    table["Comment"] = df[COL_COMMENT]


    table = table.sort_values("ETD", ascending=False)

    table = table.reset_index(drop=True)


    st.dataframe(
        table,
        use_container_width=True
    )


# ================= DOWNLOAD =================

st.download_button(
    "⬇️ Скачать отчёт",
    df.to_csv(index=False),
    "china_logistics_2026_dashboard.csv",
    "text/csv"
)

