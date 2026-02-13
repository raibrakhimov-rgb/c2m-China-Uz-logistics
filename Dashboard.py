import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

# ================= CONFIG =================

st.set_page_config(
    page_title="Сводная по вылетам",
    layout="wide"
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA/export?format=xlsx"

START_ROW = 862  # с 863 строки


# ================= HELPERS =================

def find_col(df, keys):
    for col in df.columns:
        for k in keys:
            if k.lower() in str(col).lower():
                return col
    return None


def month_ru(dt):
    months = [
        "январь","февраль","март","апрель","май","июнь",
        "июль","август","сентябрь","октябрь","ноябрь","декабрь"
    ]
    return f"{months[dt.month-1]} {dt.year}"


# ================= LOAD =================

@st.cache_data(ttl=600)
def load_data():

    df = pd.read_excel(SHEET_URL)
    df = df.iloc[START_ROW:].copy()
    df.columns = df.iloc[0]
    df = df[1:]

    df = df.reset_index(drop=True)

    return df


df = load_data()


# ================= COLUMNS =================

COL_WEIGHT = find_col(df, ["weight", "вес"])
COL_ETD = find_col(df, ["etd"])
COL_ATD = find_col(df, ["atd"])
COL_ETA = find_col(df, ["eta"])
COL_ATA = find_col(df, ["ata"])
COL_AWB = find_col(df, ["awb"])
COL_CARTON = find_col(df, ["carton"])
COL_SPLIT = find_col(df, ["дроб"])

REQUIRED = [COL_WEIGHT, COL_ETD, COL_AWB]

if None in REQUIRED:
    st.error("Не найдены обязательные колонки")
    st.write(df.columns.tolist())
    st.stop()


# ================= CLEAN =================

for c in [COL_ETD, COL_ATD, COL_ETA, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")


df = df[df[COL_ETD].dt.year == 2026]
df = df.sort_values(COL_ETD)


# ================= HEADER =================

st.title("📊 Сводная по вылетам из Материкового Китая в Узбекистан")


# ================= TABS =================

tab1, tab2, tab3 = st.tabs([
    "✈️ Вылеты",
    "📋 Список партий",
    "📦 Дробленные партии"
])


# ================= CHART =================

with tab1:

    mode = st.radio(
        "",
        ["По дням", "По неделям", "По месяцам"],
        horizontal=True
    )


    chart_df = df.copy()

    if mode == "По дням":

        chart_df["label"] = chart_df[COL_ETD].dt.strftime("%d.%m")

        grp = chart_df.groupby("label", sort=False)[COL_WEIGHT].sum().reset_index()


    elif mode == "По неделям":

        chart_df["week_start"] = chart_df[COL_ETD] - pd.to_timedelta(chart_df[COL_ETD].dt.weekday, unit="d")
        chart_df["week_end"] = chart_df["week_start"] + pd.Timedelta(days=6)

        chart_df["label"] = (
            chart_df["week_start"].dt.strftime("%d.%m") +
            "-" +
            chart_df["week_end"].dt.strftime("%d.%m")
        )

        grp = chart_df.groupby("label", sort=False)[COL_WEIGHT].sum().reset_index()


    else:  # month

        chart_df["month"] = chart_df[COL_ETD].dt.to_period("M")

        chart_df["label"] = chart_df[COL_ETD].apply(month_ru)

        grp = chart_df.groupby("label", sort=False)[COL_WEIGHT].sum().reset_index()


    grp["label"] = grp["label"].astype(str)


    chart = (
        alt.Chart(grp)
        .mark_bar(size=28)
        .encode(
            x=alt.X("label:O", title=""),
            y=alt.Y(f"{COL_WEIGHT}:Q", title="Вес (кг)"),
            tooltip=["label", COL_WEIGHT]
        )
        .properties(height=420)
    )


    st.altair_chart(chart, use_container_width=True)


# ================= LIST =================

with tab2:

    table = df.copy()

    table["ETD"] = table[COL_ETD].dt.strftime("%d.%m.%Y")
    table["ATD"] = table[COL_ATD].dt.strftime("%d.%m.%Y") if COL_ATD else ""
    table["ETA"] = table[COL_ETA].dt.strftime("%d.%m.%Y") if COL_ETA else ""
    table["ATA"] = table[COL_ATA].dt.strftime("%d.%m.%Y") if COL_ATA else ""
    table["ATA_ext"] = table[COL_ATA].dt.strftime("%H:%M") if COL_ATA else ""

    table = table.sort_values(COL_ETD, ascending=False)

    view = table[
        [
            COL_AWB,
            "ETD",
            "ATD",
            "ETA",
            "ATA",
            "ATA_ext",
            COL_WEIGHT
        ]
    ]

    view.columns = [
        "AWB",
        "ETD",
        "ATD",
        "ETA",
        "ATA",
        "ATA_ext",
        "Weight (kg)"
    ]

    view = view.reset_index(drop=True)
    view.index += 1

    st.dataframe(view, use_container_width=True)


# ================= SPLIT =================

with tab3:

    if COL_SPLIT is None:
        st.info("Нет колонки 'Дробление'")
        st.stop()


    split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

    res = []

    for awb, g in split_df.groupby(COL_AWB):

        cartons = list(g[COL_CARTON].dropna().astype(int))

        res.append({
            "AWB": awb,
            "Q-ty of flights": len(g),
            "Total No of cartons": sum(cartons),
            "Q-ty of separate cartons": ", ".join(map(str, cartons))
        })


    out = pd.DataFrame(res)

    out.index += 1
    out.insert(0, "№", out.index)

    st.dataframe(out, use_container_width=True)
