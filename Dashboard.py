import streamlit as st
import pandas as pd
import altair as alt
import calendar


# ================= CONFIG =================

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"

START_ROW = 862   # данные с 863 строки


MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


# ================= LOAD =================

@st.cache_data(ttl=600)
def load_data():

    df = pd.read_csv(
        SHEET_URL,
        header=1      # заголовки во 2-й строке
    )

    # чистим названия
    df.columns = df.columns.str.strip()

    # берём данные с 863 строки
    df = df.iloc[START_ROW:].reset_index(drop=True)

    # убираем пустые строки
    df = df.dropna(how="all")

    return df


# ===== load first =====
df = load_data()


# ================= AUTO COLUMN MAP =================

def find_col(keywords):

    for col in df.columns:

        name = str(col).lower().strip()

        for k in keywords:
            if k in name:
                return col

    return None


COL_WEIGHT = find_col(["weight", "вес", "kg"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight", "рейс"])
COL_COMMENT = find_col(["comment", "коммент"])


REQUIRED = {
    "Weight": COL_WEIGHT,
    "ETD": COL_ETD,
    "ATD": COL_ATD,
    "ETA": COL_ETA,
    "ATA": COL_ATA,
    "AWB": COL_AWB,
    "Flight": COL_FLIGHT,
}

missing = [k for k, v in REQUIRED.items() if v is None]

if missing:
    st.error(f"❌ Не найдены колонки: {', '.join(missing)}")
    st.write("Найденные колонки:", df.columns.tolist())
    st.stop()


# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce").fillna(0)


for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)


# только 2026+
df = df[df[COL_ETD].dt.year >= 2026]


# ================= STATUS =================

def get_status(row):

    if pd.notna(row[COL_ATA]):
        return "Delivered"

    if pd.notna(row[COL_ATD]):
        return "In Transit"

    return "Scheduled"


df["Status"] = df.apply(get_status, axis=1)


# ================= METRICS =================

total_batches = len(df)
total_weight = int(df[COL_WEIGHT].sum())

in_transit = len(df[df["Status"] == "In Transit"])
delivered = len(df[df["Status"] == "Delivered"])


df["Transit_days"] = (df[COL_ATA] - df[COL_ETD]).dt.days
avg_transit = df["Transit_days"].mean()


sla = (df["Transit_days"] <= 7).mean() * 100


# ================= HEADER =================

st.title("✈️ Сводная по вылетам из Материкового Китая в Узбекистан")


c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", total_batches)
c2.metric("⚖️ Вес (кг)", total_weight)
c3.metric("✈️ В пути", in_transit)
c4.metric("🏢 Доставлено", delivered)
c5.metric("⏱ Транзит (дн)", round(avg_transit, 1))
c6.metric("🎯 SLA %", round(sla, 1))


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "📊 Вылеты",
    "⏰ Просрочки",
    "📋 Список партий"
])


# =================================================
# TAB 1 — CHART
# =================================================

with tab1:

    st.subheader("✈️ Вылеты")


    view = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True
    )


    base = df[[COL_ETD, COL_WEIGHT]].dropna().copy()
    base = base.sort_values(COL_ETD)



    # -------- DAYS --------

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

        x_enc = alt.X(
            "date:T",
            title="Дата",
            axis=alt.Axis(format="%d.%m", labelAngle=-45)
        )



    # -------- WEEKS --------

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
            + "-"
            + chart_df["week_end"].dt.strftime("%d.%m")
        )

        chart_df["date"] = chart_df["label"]

        chart_df = chart_df[["date", "label", COL_WEIGHT]]
        chart_df.columns = ["date", "label", "weight"]

        x_enc = alt.X(
            "date:N",
            title="Период",
            sort=None,
            scale=alt.Scale(
                paddingInner=0,
                paddingOuter=0,
            )
        )



    # -------- MONTHS --------

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
            chart_df["start"].dt.month.map(MONTHS_RU)
            + " "
            + chart_df["start"].dt.year.astype(str)
        )

        chart_df["date"] = chart_df["label"]

        chart_df = chart_df[["date", "label", COL_WEIGHT, "start"]]
        chart_df.columns = ["date", "label", "weight", "start"]

        chart_df = chart_df.sort_values("start")

        x_enc = alt.X(
            "date:N",
            title="Период",
            sort=None,
            scale=alt.Scale(
                paddingInner=0,
                paddingOuter=0,
            )
        )



    chart_df = chart_df.reset_index(drop=True)



    chart = (
        alt.Chart(chart_df)
        .mark_bar(size=22)
        .encode(
            x=x_enc,

            y=alt.Y(
                "weight:Q",
                title="Вес (кг)"
            ),

            tooltip=[
                alt.Tooltip("label:N", title="Период"),
                alt.Tooltip("weight:Q", title="Вес (кг)")
            ]
        )
      .properties(
    height=420,
    width=alt.Step(45))


    st.altair_chart(chart, use_container_width=True)


# =================================================
# TAB 2 — DELAYS
# =================================================

with tab2:

    st.subheader("⏰ Просрочки > 1 дня")


    delay = df.copy()

    delay["Delay_Arrival_d"] = (delay[COL_ATA] - delay[COL_ETA]).dt.days
    delay["Delay_Departure_d"] = (delay[COL_ATD] - delay[COL_ETD]).dt.days

    delay = delay[delay["Delay_Arrival_d"] > 0]


    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        delay[c] = delay[c].dt.strftime("%d.%m.%Y")


    delay = delay[[
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        "Delay_Departure_d",
        "Delay_Arrival_d",
        COL_COMMENT
    ]]


    delay = delay.rename(columns={
        COL_AWB: "AWB",
        COL_FLIGHT: "Flight",
        COL_ETD: "ETD",
        COL_ATD: "ATD",
        COL_ETA: "ETA",
        COL_ATA: "ATA",
        "Delay_Departure_d": "Delay Departure (d)",
        "Delay_Arrival_d": "Delay Arrival (d)",
        COL_COMMENT: "Comment"
    })


    st.dataframe(delay, use_container_width=True, hide_index=True)


# =================================================
# TAB 3 — TABLE
# =================================================

with tab3:

    st.subheader("📋 Список партий")


    table = df.copy()

    table = table.sort_values(COL_ETD, ascending=False)


    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        table[c] = table[c].dt.strftime("%d.%m.%Y")


    table["ATA_ext"] = table[COL_ATA].dt.strftime("%H:%M")


    table = table[[
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        "ATA_ext",
        COL_WEIGHT,
        "Status",
        COL_COMMENT
    ]]


    table = table.rename(columns={
        COL_AWB: "AWB",
        COL_FLIGHT: "Flight",
        COL_WEIGHT: "Weight (kg)",
        COL_COMMENT: "Comment"
    })


    st.dataframe(table, use_container_width=True, hide_index=True)

