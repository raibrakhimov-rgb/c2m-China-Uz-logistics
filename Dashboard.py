import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

# ==============================
# CONFIG
# ==============================

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ==============================
# LOAD DATA
# ==============================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.iloc[866:].reset_index(drop=True)

    df.columns = df.columns.astype(str).str.strip()

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    return df


df = load_data()

# ==============================
# FIND COLUMNS
# ==============================

def find(keys):
    for col in df.columns:
        name = col.lower()
        for k in keys:
            if k in name:
                return col
    return None


COL_PROJECT = find(["project", "проект"])
COL_WEIGHT = find(["weight"])
COL_CARTON = find(["carton"])
COL_DATE = find(["outbound date"])
COL_ETD = find(["etd"])
COL_ATD = find(["atd"])
COL_ETA = find(["eta"])
COL_ATA = find(["ata"])
COL_ATA_TIME = find(["ata_ext"])
COL_AWB = find(["awb"])
COL_FLIGHT = find(["flight"])
COL_SPLIT = find(["дроб"])
COL_VIA = find(["via"])
COL_REMARKS = find(["remarks"])
COL_HUB_DATE = find(["поступления на склад хаб"])
COL_DAYS_TAS = find(["терминала tas"])
COL_DAYS_HUB = find(["до хаба"])

# ==============================
# FORMAT DATA
# ==============================

date_cols = [COL_DATE, COL_ETD, COL_ATD, COL_ETA, COL_ATA]

for c in date_cols:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

if COL_WEIGHT:
    df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

if COL_CARTON:
    df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

if COL_DAYS_HUB:
    df[COL_DAYS_HUB] = pd.to_numeric(df[COL_DAYS_HUB], errors="coerce").round()

if COL_DAYS_TAS:
    df[COL_DAYS_TAS] = pd.to_numeric(df[COL_DAYS_TAS], errors="coerce").round()

df = df.dropna(subset=[COL_DATE, COL_WEIGHT])

# ==============================
# HEADER
# ==============================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")

# ==============================
# FILTER
# ==============================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]

# ==============================
# PERIOD SELECT
# ==============================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

if period == "По дням":

    chart_df["label"] = chart_df[COL_DATE]

elif period == "По неделям":

    start = pd.to_datetime(chart_df[COL_DATE])
    start = start - pd.to_timedelta(start.dt.weekday, unit="D")
    end = start + pd.Timedelta(days=6)

    chart_df["label"] = (
        start.dt.strftime("%d.%m")
        + "-"
        + end.dt.strftime("%d.%m")
    )

else:

    months = {
        1:"январь",2:"февраль",3:"март",
        4:"апрель",5:"май",6:"июнь",
        7:"июль",8:"август",9:"сентябрь",
        10:"октябрь",11:"ноябрь",12:"декабрь"
    }

    chart_df["label"] = (
        pd.to_datetime(chart_df[COL_DATE]).dt.month.map(months)
        + " "
        + pd.to_datetime(chart_df[COL_DATE]).dt.year.astype(str)
    )

grouped = chart_df.groupby("label")[COL_WEIGHT].sum().reset_index()

# сортировка
if period == "По дням":
    grouped = grouped.sort_values("label")

# ==============================
# HORIZONTAL INTERACTIVE CHART
# ==============================

fig = px.bar(
    grouped,
    x=COL_WEIGHT,
    y="label",
    orientation="h",
    text=COL_WEIGHT
)

fig.update_layout(height=900)

st.plotly_chart(fig, use_container_width=True)

# ==============================
# TABS
# ==============================

tab1, tab2 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии"
])

# ==============================
# MAIN TABLE
# ==============================

with tab1:

    table = df.copy()

    table = table.rename(columns={
        COL_PROJECT: "Проект",
        COL_CARTON: "Outbound carton",
        COL_WEIGHT: "Outbound weight (kg)",
        COL_DATE: "Outbound date",
        COL_AWB: "Booking/AWB No.",
        COL_FLIGHT: "Flight No.",
        COL_VIA: "VIA",
        COL_ETD: "ETD",
        COL_ATD: "ATD",
        COL_ETA: "ETA",
        COL_ATA: "ATA",
        COL_ATA_TIME: "ATA_time",
        COL_HUB_DATE: "Поступления на склад ХАБ",
        COL_DAYS_TAS: "Дней до прибытия до TAS",
        COL_DAYS_HUB: "Дней до прибытия до ХАБа",
        COL_REMARKS: "Remarks"
    })

    if "№" in table.columns:
        table = table.drop(columns=["№"])

    table.insert(0, "№", range(1, len(table)+1))

    order = [
        "№",
        "Проект",
        "Outbound carton",
        "Outbound weight (kg)",
        "Outbound date",
        "Booking/AWB No.",
        "Flight No.",
        "VIA",
        "ETD",
        "ATD",
        "ETA",
        "ATA",
        "ATA_time",
        "Поступления на склад ХАБ",
        "Дней до прибытия до TAS",
        "Дней до прибытия до ХАБа",
        "Remarks"
    ]

    order = [c for c in order if c in table.columns]

    table = table[order]

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

# ==============================
# SPLIT TABLE
# ==============================

with tab2:

    if COL_SPLIT is None:

        st.info("Нет данных о дроблении")

    else:

        split_df = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split_df.groupby(COL_AWB):

            cartons = g[COL_CARTON].dropna().tolist()

            ata_split = g[COL_ATA].dropna().astype(str).tolist()

            rows.append({
                "AWB": awb,
                "Flights": len(g),
                "Total cartons": int(sum(cartons)),
                "Separate cartons": ", ".join(map(str, cartons)),
                "ATA (при дроблении)": ", ".join(ata_split)
            })

        split_table = pd.DataFrame(rows)

        if "№" in split_table.columns:
            split_table = split_table.drop(columns=["№"])

        split_table.insert(0, "№", range(1, len(split_table)+1))

        st.dataframe(
            split_table,
            use_container_width=True,
            hide_index=True
        )
