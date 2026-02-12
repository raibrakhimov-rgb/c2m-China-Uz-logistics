import streamlit as st
import pandas as pd


SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=csv&gid=1730191747"


# ================= LOAD =================

@st.cache_data(ttl=300)
def load_data():
    # header=1 → заголовки во 2 строке
    df = pd.read_csv(SHEET_URL, header=1)

    # Берём только с 863 строки
    df = df.iloc[862:].copy()

    return df


df = load_data()

st.set_page_config("China Logistics Dashboard", layout="wide")
st.title("✈️ China Logistics Control Center")

if df.empty:
    st.stop()


# ================= CLEAN =================

df.columns = df.columns.str.strip()


# Удаляем первую пустую колонку (нумерация)
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


# ================= DATES =================

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")


# ================= CLEAN WEIGHT =================

if COL_WEIGHT:
    df[COL_WEIGHT] = (
        df[COL_WEIGHT]
        .astype(str)
        .str.replace(r"[^\d\.]", "", regex=True)
    )

    df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")


# ================= FILTER 2026+ =================

if COL_ETD:
    df = df[df[COL_ETD].dt.year >= 2026]


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


# ================= PLAN / FACT =================

if COL_ETD and COL_ATD:
    df["Delay_Departure_h"] = (
        (df[COL_ATD] - df[COL_ETD]).dt.total_seconds() / 3600
    )


if COL_ETA and COL_ATA:
    df["Delay_Arrival_h"] = (
        (df[COL_ATA] - df[COL_ETA]).dt.total_seconds() / 3600
    )


# ================= TRANSIT =================

if COL_ATD and COL_ATA:

    df["Transit_days"] = (
        (df[COL_ATA] - df[COL_ATD]).dt.total_seconds() / 86400
    )


# ================= SLA =================

SLA_LIMIT = 24


if "Delay_Arrival_h" in df.columns:
    df["SLA_OK"] = df["Delay_Arrival_h"] <= SLA_LIMIT


# ================= FORMAT DATES =================

def fmt_date(col):
    if col and col in df.columns:
        return df[col].dt.strftime("%d.%m.%Y")
    return None


ETD_FMT = fmt_date(COL_ETD)
ETA_FMT = fmt_date(COL_ETA)
ATD_FMT = fmt_date(COL_ATD)
ATA_FMT = fmt_date(COL_ATA)


# ATA_ext → только время

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


if "Transit_days" in df.columns:
    c5.metric("⏱ Транзит (дн)", round(df["Transit_days"].mean(), 1))
else:
    c5.metric("⏱ Транзит", "-")


if "SLA_OK" in df.columns:
    sla = round(df["SLA_OK"].mean() * 100, 1)
    c6.metric("🎯 SLA %", sla)
else:
    c6.metric("🎯 SLA", "-")


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "📈 Вылеты",
    "⏰ Просрочки",
    "📋 Список партий"
])


# ================= TAB 1 =================

with tab1:

    if COL_ETD and COL_WEIGHT:

        chart = (
            df
            .groupby(df[COL_ETD].dt.date)[COL_WEIGHT]
            .sum()
            .sort_index()
        )

        st.line_chart(chart)


# ================= TAB 2 =================

with tab2:

    st.subheader("Просрочки > 24ч")

    if "Delay_Arrival_h" in df.columns:

        delay = df[df["Delay_Arrival_h"] > SLA_LIMIT]

        # Убираем мусорные колонки
        delay = delay[[
            COL_AWB,
            COL_FLIGHT,
            COL_ETD,
            COL_ETA,
            COL_ATA,
            "Delay_Arrival_h",
            COL_COMMENT
        ]]

        st.dataframe(delay, use_container_width=True)


# ================= TAB 3 =================

with tab3:

    st.subheader("Список партий")


    table = pd.DataFrame()


    if COL_AWB:
        table["AWB"] = df[COL_AWB]

    if COL_FLIGHT:
        table["Flight"] = df[COL_FLIGHT]

    if ETD_FMT is not None:
        table["ETD"] = ETD_FMT

    if ETA_FMT is not None:
        table["ETA"] = ETA_FMT

    if ATD_FMT is not None:
        table["ATD"] = ATD_FMT

    if ATA_FMT is not None:
        table["ATA"] = ATA_FMT

    if COL_ATA_EXT:
        table["ATA_ext"] = df[COL_ATA_EXT]

    if COL_WEIGHT:
        table["Weight (kg)"] = df[COL_WEIGHT]

    table["Status"] = df["Status"]

    if COL_COMMENT:
        table["Comment"] = df[COL_COMMENT]


    st.dataframe(
        table.sort_values("ETD", ascending=False),
        use_container_width=True
    )


# ================= DOWNLOAD =================

st.download_button(
    "⬇️ Скачать отчёт",
    df.to_csv(index=False),
    "china_logistics_2026_clean.csv",
    "text/csv"
)
