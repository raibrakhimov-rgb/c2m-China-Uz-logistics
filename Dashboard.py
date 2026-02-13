import streamlit as st
import pandas as pd
import altair as alt


# ================= CONFIG =================

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"

START_ROW = 862


MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


# ================= LOAD DATA =================

@st.cache_data(ttl=600)
def load_data():

    df = pd.read_csv(
        SHEET_URL,
        header=1
    )

    df.columns = df.columns.str.strip()

    df = df.iloc[START_ROW:].reset_index(drop=True)

    df = df.dropna(how="all")

    return df


df = load_data()


# ================= FIND COLUMNS =================

def find_col(keys):

    for col in df.columns:

        name = str(col).lower()

        for k in keys:
            if k in name:
                return col

    return None


COL_WEIGHT = find_col(["weight", "вес"])
COL_ETD = find_col(["etd"])
COL_ATD = find_col(["atd"])
COL_ETA = find_col(["eta"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_FLIGHT = find_col(["flight"])
COL_PROJECT = find_col(["проект"])
COL_SPLIT = find_col(["дроб"])
COL_CARTON = find_col(["carton"])
COL_COMMENT = find_col(["коммент"])


REQUIRED = [COL_WEIGHT, COL_ETD, COL_ATD, COL_ETA, COL_ATA, COL_AWB, COL_FLIGHT]

if any(x is None for x in REQUIRED):

    st.error("❌ Не найдены обязательные колонки")
    st.write(df.columns.tolist())
    st.stop()


# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce").fillna(0)

for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

df = df.dropna(subset=[COL_ETD])

df = df[df[COL_ETD].dt.year >= 2026]


# ================= PROJECT FILTER =================

st.title("✈️ Сводная по вылетам из Материкового Китая в Узбекистан")

projects = ["Все"]

if COL_PROJECT:
    projects += sorted(df[COL_PROJECT].dropna().unique())

selected = st.radio("Проект:", projects, horizontal=True)

if selected != "Все" and COL_PROJECT:
    df = df[df[COL_PROJECT] == selected]


# ================= METRICS =================

delivered = df[df[COL_ATA].notna()]
in_transit = df[df[COL_ATA].isna()]

total_weight = int(df[COL_WEIGHT].sum())

avg_transit = (
    (delivered[COL_ATA] - delivered[COL_ETD])
    .dt.days
    .mean()
)

sla = (
    (delivered[COL_ATA] <= delivered[COL_ETA])
    .mean() * 100
    if len(delivered) else 0
)


c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", len(df))
c2.metric("⚖️ Вес (кг)", total_weight)
c3.metric("✈️ В пути", len(in_transit))
c4.metric("📬 Доставлено", len(delivered))
c5.metric("⏱ Транзит (дн)", round(avg_transit, 1) if avg_transit else 0)
c6.metric("🎯 SLA %", round(sla, 1))


# ================= TABS =================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Вылеты",
    "⏰ Просрочки",
    "📋 Список партий",
    "📦 Дробленные партии"
])


# =================================================
# TAB 1 — CHART
# =================================================

with tab1:

    view = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True
    )


    base = df[[COL_ETD, COL_WEIGHT]].copy()
    base = base.dropna()


    # ---------- DAYS ----------

    if view == "По дням":

        chart_df = (
            base
            .groupby(base[COL_ETD].dt.date)[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        chart_df.columns = ["date", "weight"]

        chart_df["label"] = chart_df["date"].astype(str)



    # ---------- WEEKS ----------

    elif view == "По неделям":

        base["week"] = base[COL_ETD].dt.to_period("W")

        chart_df = (
            base
            .groupby("week")[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        chart_df["start"] = chart_df["week"].dt.start_time
        chart_df["end"] = chart_df["week"].dt.end_time

        chart_df["label"] = (
            chart_df["start"].dt.strftime("%d.%m")
            + "-"
            + chart_df["end"].dt.strftime("%d.%m")
        )

        chart_df["weight"] = chart_df[COL_WEIGHT]



    # ---------- MONTHS ----------

    else:

        base["month"] = base[COL_ETD].dt.to_period("M")

        chart_df = (
            base
            .groupby("month")[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        chart_df["dt"] = chart_df["month"].dt.to_timestamp()

        chart_df["label"] = chart_df["dt"].apply(
            lambda x: f"{MONTHS_RU[x.month]} {x.year}"
        )

        chart_df["weight"] = chart_df[COL_WEIGHT]

        chart_df = chart_df.sort_values("dt")


    chart_df = chart_df.reset_index(drop=True)

    chart_df["x"] = chart_df.index.astype(str)



    # ---------- CHART ----------

    chart = (
        alt.Chart(chart_df)
        .mark_bar(size=45)
        .encode(
            x=alt.X("x:O", title="Период"),
            y=alt.Y("weight:Q", title="Вес (кг)"),
            tooltip=[
                alt.Tooltip("label:N", title="Период"),
                alt.Tooltip("weight:Q", title="Вес (кг)")
            ]
        )
        .properties(height=420)
    )

    st.altair_chart(chart, use_container_width=True)


# =================================================
# TAB 2 — DELAYS
# =================================================

with tab2:

    delay = df.copy()

    delay["Delay_Arrival"] = (delay[COL_ATA] - delay[COL_ETA]).dt.days
    delay["Delay_Departure"] = (delay[COL_ATD] - delay[COL_ETD]).dt.days

    delay = delay[delay["Delay_Arrival"] > 0]


    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        delay[c] = delay[c].dt.strftime("%d.%m.%Y")


    delay = delay[[
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        "Delay_Departure",
        "Delay_Arrival",
        COL_COMMENT
    ]]


    st.dataframe(delay, use_container_width=True, hide_index=True)


# =================================================
# TAB 3 — LIST
# =================================================

with tab3:

    table = df.copy()

    table = table.sort_values(COL_ETD, ascending=False)


    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        table[c] = table[c].dt.strftime("%d.%m.%Y")


    table["ATA_ext"] = pd.to_datetime(
        table[COL_ATA],
        errors="coerce"
    ).dt.strftime("%H:%M")


    table = table[[
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        "ATA_ext",
        COL_WEIGHT,
        COL_COMMENT
    ]]


    table = table.rename(columns={
        COL_AWB: "AWB",
        COL_FLIGHT: "Flight",
        COL_WEIGHT: "Weight (kg)",
        COL_COMMENT: "Comment"
    })


    st.dataframe(table, use_container_width=True, hide_index=True)


# =================================================
# TAB 4 — SPLIT
# =================================================

with tab4:

    if COL_SPLIT and COL_CARTON:

        tmp = df.copy()

        tmp[COL_SPLIT] = tmp[COL_SPLIT].astype(str).str.lower()

        split = tmp[tmp[COL_SPLIT].str.contains("да", na=False)]

        result = (
            split
            .groupby(COL_AWB)
            .agg(
                flights=(COL_ETD, "count"),
                cartons=(COL_CARTON, "sum"),
                parts=(COL_CARTON, lambda x: ", ".join(x.astype(str)))
            )
            .reset_index()
        )

        result = result[result["flights"] >= 2]


        st.dataframe(result, use_container_width=True)

    else:
        st.info("Колонки дробления не найдены")
