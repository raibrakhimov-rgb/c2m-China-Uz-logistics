import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

# ================= CONFIG =================

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)

# ================= HELPERS =================


def normalize(col):
    return str(col).strip().lower()


def find_column(keywords, columns):
    for col in columns:
        for k in keywords:
            if k in normalize(col):
                return col
    return None


RU_MONTHS = {
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


# ================= LOAD DATA =================


@st.cache_data(ttl=600)
def load_data():
    df = pd.read_csv(SHEET_CSV_URL, header=1)
    df = df.dropna(how="all")
    return df


df = load_data()

# ================= FIND COLUMNS =================

cols = list(df.columns)

COL_WEIGHT = find_column(["weight", "вес"], cols)
COL_ETD = find_column(["etd"], cols)
COL_ATD = find_column(["atd"], cols)
COL_ETA = find_column(["eta"], cols)
COL_ATA = find_column(["ata"], cols)
COL_AWB = find_column(["awb"], cols)
COL_FLIGHT = find_column(["flight"], cols)
COL_PROJECT = find_column(["проект"], cols)
COL_SPLIT = find_column(["дроб"], cols)
COL_CARTON = find_column(["carton"], cols)
COL_COMMENT = find_column(["коммент"], cols)

required = [
    COL_WEIGHT, COL_ETD, COL_ATD, COL_ETA,
    COL_ATA, COL_AWB, COL_FLIGHT
]

missing = [c for c in required if c is None]

if missing:
    st.error("❌ Не найдены обязательные колонки")
    st.write("Найденные:", df.columns.tolist())
    st.stop()


# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)


df = df.dropna(subset=[COL_ETD])


# ================= PROJECT FILTER =================

st.title("📊 Сводная по вылетам из Материкового Китая в Узбекистан")

projects = ["Все"]

if COL_PROJECT:
    projects += sorted(df[COL_PROJECT].dropna().unique())

selected_project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if selected_project != "Все" and COL_PROJECT:
    df = df[df[COL_PROJECT] == selected_project]


# ================= METRICS =================

delivered = df[df[COL_ATA].notna()]
in_transit = df[df[COL_ATA].isna()]

total_weight = int(df[COL_WEIGHT].sum())

avg_transit = (
    (delivered[COL_ATA] - delivered[COL_ATD])
    .dt.days
    .mean()
)

sla = (
    (delivered[COL_ATA] <= delivered[COL_ETA])
    .mean() * 100
    if len(delivered) > 0 else 0
)

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", len(df))
c2.metric("⚖️ Вес (кг)", total_weight)
c3.metric("✈️ В пути", len(in_transit))
c4.metric("📬 Доставлено", len(delivered))
c5.metric("⏱ Транзит (дн)", round(avg_transit, 1) if avg_transit else 0)
c6.metric("🎯 SLA %", round(sla, 1))


# ================= GROUPING =================

st.markdown("### ✈️ Вылеты")

grouping = st.radio(
    "",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

base = df[[COL_ETD, COL_WEIGHT]].copy()
base["date"] = base[COL_ETD].dt.date


# ================= DAILY =================

if grouping == "По дням":

    chart_df = (
        base
        .groupby("date")[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values("date")
    )

    chart_df["label"] = chart_df["date"].astype(str)


# ================= WEEKLY =================

elif grouping == "По неделям":

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
        chart_df["start"].dt.strftime("%d.%m") +
        "-" +
        chart_df["end"].dt.strftime("%d.%m")
    )

    chart_df = chart_df.sort_values("start")


# ================= MONTHLY =================

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
        lambda x: f"{RU_MONTHS[x.month]} {x.year}"
    )

    chart_df = chart_df.sort_values("dt")


# ================= BAR CHART =================

chart_df["x"] = range(len(chart_df))

chart = (
    alt.Chart(chart_df)
    .mark_bar(size=50)
    .encode(
        x=alt.X("x:O", title="Период"),
        y=alt.Y("weight:Q", title="Вес (кг)"),
        tooltip=["label", "weight"]
    )
    .properties(height=420)
)



st.altair_chart(chart, use_container_width=True)



# ================= TABS =================

tab1, tab2, tab3, tab4 = st.tabs([
    "⏰ Просрочки",
    "📋 Список партий",
    "📦 Дробленные партии",
    "📊 Данные"
])


# ================= DELAYS =================

with tab1:

    st.subheader("Просрочки > 24ч")

    late = df[
        (df[COL_ATA].notna()) &
        (df[COL_ATA] > df[COL_ETA])
    ].copy()

    if not late.empty:

        late["Delay_days"] = (
            (late[COL_ATA] - late[COL_ETA])
            .dt.days
        )

        late["Delay_dep"] = (
            (late[COL_ATD] - late[COL_ETD])
            .dt.days
        )

        for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
            late[c] = late[c].dt.strftime("%d.%m.%Y")

        st.dataframe(
            late[
                [
                    COL_AWB,
                    COL_FLIGHT,
                    COL_ETD,
                    COL_ATD,
                    COL_ETA,
                    COL_ATA,
                    "Delay_dep",
                    "Delay_days",
                    COL_COMMENT
                ]
            ],
            use_container_width=True
        )

    else:
        st.success("Просрочек нет")


# ================= LIST =================

with tab2:

    st.subheader("Список партий")

    table = df.copy()

    table = table.sort_values(COL_ETD, ascending=False)

    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        table[c] = table[c].dt.strftime("%d.%m.%Y")

    st.dataframe(
        table[
            [
                COL_AWB,
                COL_FLIGHT,
                COL_ETD,
                COL_ATD,
                COL_ETA,
                COL_ATA,
                COL_WEIGHT,
                COL_PROJECT,
                COL_COMMENT
            ]
        ],
        use_container_width=True
    )


# ================= SPLIT =================

with tab3:

    st.subheader("Дробленные партии")

    if COL_SPLIT and COL_CARTON:

        tmp = df.copy()
        tmp[COL_SPLIT] = tmp[COL_SPLIT].astype(str).str.lower()

        split_df = tmp[tmp[COL_SPLIT].str.contains("да", na=False)]

        split = (
            split_df
            .groupby(COL_AWB)
            .agg(
                flights=(COL_ETD, "count"),
                cartons=(COL_CARTON, "sum"),
                details=(COL_CARTON, lambda x: ", ".join(x.astype(str)))
            )
            .reset_index()
        )

        split = split[split["flights"] >= 2]

        if split.empty:
            st.success("Дроблений нет")
        else:
            st.dataframe(
                split.rename(columns={
                    COL_AWB: "AWB",
                    "flights": "Рейсов",
                    "cartons": "Коробов",
                    "details": "Разбивка"
                }),
                use_container_width=True
            )

    else:
        st.warning("Колонки дробления не найдены")


# ================= RAW =================

with tab4:

    st.subheader("Исходные данные")

    st.dataframe(df, use_container_width=True)




