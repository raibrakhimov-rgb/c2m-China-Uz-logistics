import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ================= CONFIG =================

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"

START_ROW = 862   # данные с 863 строки (0-based)


# ================= LOAD DATA =================

@st.cache_data(ttl=600)
def load_data():
    df = pd.read_csv(SHEET_URL)
    df = df.iloc[START_ROW:].reset_index(drop=True)
    return df


df = load_data()


# ================= AUTO COLUMN MAP =================

def find_col(keywords):
    for col in df.columns:
        name = col.lower().strip()
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
COL_COMMENT = find_col(["comment", "коммент", "备注"])


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


# ================= CLEAN DATA =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce").fillna(0)


for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    df[c] = pd.to_datetime(df[c], errors="coerce")


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


# transit days
df["Transit_days"] = (df[COL_ATA] - df[COL_ETD]).dt.days
avg_transit = df["Transit_days"].mean()


# SLA (до 7 дней = ок)
sla = (df["Transit_days"] <= 7).mean() * 100


# ================= HEADER =================

st.title("📊 Сводная по вылетам из Материкового Китая в Узбекистан")


c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("📦 Партии", total_batches)
c2.metric("⚖️ Вес (кг)", total_weight)
c3.metric("✈️ В пути", in_transit)
c4.metric("🏢 Доставлено", delivered)
c5.metric("⏱ Транзит (дн)", round(avg_transit, 1))
c6.metric("🎯 SLA %", round(sla, 1))


# ================= TABS =================

tab1, tab2, tab3 = st.tabs(["✈️ Вылеты", "⏰ Просрочки", "📋 Список партий"])


# ================= HELPERS =================

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


# ================= TAB 1 — CHART =================

with tab1:

    mode = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True
    )

    data = df.copy()


    # -------- DAILY --------
    if mode == "По дням":

        grp = (
            data
            .groupby(data[COL_ETD].dt.date)[COL_WEIGHT]
            .sum()
            .reset_index()
        )

        grp["Label"] = grp[COL_ETD].astype(str)


    # -------- WEEKLY --------
    elif mode == "По неделям":

        data["week"] = data[COL_ETD].dt.to_period("W")

        grp = data.groupby("week")[COL_WEIGHT].sum().reset_index()

        def format_week(p):
            s = p.start_time.strftime("%d.%m")
            e = p.end_time.strftime("%d.%m")
            return f"{s}-{e}"

        grp["Label"] = grp["week"].apply(format_week)


    # -------- MONTHLY --------
    else:

        data["month"] = data[COL_ETD].dt.to_period("M")

        grp = data.groupby("month")[COL_WEIGHT].sum().reset_index()

        def format_month(p):
            m = MONTHS_RU[p.month]
            return f"{m} {p.year}"

        grp["Label"] = grp["month"].apply(format_month)


    grp = grp.sort_index()


    fig = px.bar(
        grp,
        x="Label",
        y=COL_WEIGHT,
        labels={
            "Label": "Период",
            COL_WEIGHT: "Вес (кг)"
        }
    )


    fig.update_layout(
        bargap=0,
        bargroupgap=0,
        height=500
    )


    st.plotly_chart(fig, use_container_width=True)



# ================= TAB 2 — DELAYS =================

with tab2:

    delays = df.copy()

    delays["Arrival_delay"] = (delays[COL_ATA] - delays[COL_ETA]).dt.days
    delays["Depart_delay"] = (delays[COL_ATD] - delays[COL_ETD]).dt.days


    late = delays[delays["Arrival_delay"] > 0]


    show = late[[
        COL_AWB,
        COL_FLIGHT,
        COL_ETD,
        COL_ATD,
        COL_ETA,
        COL_ATA,
        "Arrival_delay",
        "Depart_delay",
        COL_COMMENT
    ]].copy()


    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        show[c] = show[c].dt.strftime("%d.%m.%Y")


    show = show.rename(columns={
        COL_AWB: "AWB",
        COL_FLIGHT: "Flight",
        COL_ETD: "ETD",
        COL_ATD: "ATD",
        COL_ETA: "ETA",
        COL_ATA: "ATA",
        "Arrival_delay": "Delay Arrival (days)",
        "Depart_delay": "Delay Departure (days)",
        COL_COMMENT: "Comment"
    })


    st.subheader("Просрочки > 1 дня")

    st.dataframe(show, use_container_width=True)



# ================= TAB 3 — TABLE =================

with tab3:

    table = df.copy()


    table["ATA_ext"] = table[COL_ATA].dt.strftime("%H:%M")


    for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
        table[c] = table[c].dt.strftime("%d.%m.%Y")


    table = table.sort_values(
        by=COL_ETD,
        ascending=False
    )


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
        COL_ETD: "ETD",
        COL_ATD: "ATD",
        COL_ETA: "ETA",
        COL_ATA: "ATA",
        COL_WEIGHT: "Weight (kg)",
        COL_COMMENT: "Comment"
    })


    st.subheader("Список партий")

    st.dataframe(table, use_container_width=True)
