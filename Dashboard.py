import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

st.set_page_config(page_title="China → Uzbekistan Logistics", layout="wide")

# ================= CONFIG =================

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"


# ================= LOAD DATA =================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.dropna(how="all")

    df.columns = df.columns.astype(str).str.strip()

    # только данные 2026+
    df = df.iloc[866:].reset_index(drop=True)

    return df


df = load_data()


# ================= FIND COLS =================

def find(keys):
    for col in df.columns:
        c = col.lower()
        for k in keys:
            if k in c:
                return col
    return None


COL_CARTON = find(["carton"])
COL_WEIGHT = find(["weight"])
COL_DATE = find(["outbound date"])
COL_AWB = find(["awb"])
COL_PROJECT = find(["project", "проект"])
COL_SPLIT = find(["дроб"])
COL_ETD = find(["etd"])
COL_ETA = find(["eta"])
COL_ATD = find(["atd"])
COL_ATA = find(["ata"])
COL_FLIGHT = find(["flight"])
COL_VIA = find(["via"])


# ================= CLEAN =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")

for c in [COL_DATE, COL_ETD, COL_ETA, COL_ATD, COL_ATA]:
    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date


df = df.dropna(subset=[COL_DATE, COL_WEIGHT])


# ================= TITLE =================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")


# ================= KPI =================

col1, col2, col3 = st.columns(3)

col1.metric("Количество рейсов", len(df))
col2.metric("Общий вес (кг)", f"{int(df[COL_WEIGHT].sum()):,}")
col3.metric("Средний вес рейса", f"{int(df[COL_WEIGHT].mean()):,}")


# ================= FILTER PROJECT =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

selected_project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if selected_project != "Все":
    df = df[df[COL_PROJECT] == selected_project]


# ================= GROUP SELECT =================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)


chart = df.copy()


# ================= GROUPING =================

if period == "По дням":

    grouped = (
        chart
        .groupby(COL_DATE)[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values(COL_DATE)
    )

    grouped["label"] = grouped[COL_DATE].astype(str)


elif period == "По неделям":

    chart["week_start"] = chart[COL_DATE] - pd.to_timedelta(
        pd.to_datetime(chart[COL_DATE]).dt.weekday,
        unit="D"
    )

    chart["week_end"] = chart["week_start"] + pd.Timedelta(days=6)

    grouped = (
        chart
        .groupby(["week_start", "week_end"])[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values("week_start")
    )

    grouped["label"] = (
        grouped["week_start"].astype(str)
        + " - "
        + grouped["week_end"].astype(str)
    )


else:

    chart["month"] = pd.to_datetime(chart[COL_DATE]).dt.to_period("M")

    grouped = (
        chart
        .groupby("month")[COL_WEIGHT]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    grouped["label"] = grouped["month"].astype(str)


# ================= INTERACTIVE CHART =================

fig = px.bar(
    grouped,
    x="label",
    y=COL_WEIGHT,
    text=COL_WEIGHT
)

fig.update_layout(
    height=500,
    xaxis_title="",
    yaxis_title="Вес (кг)",
    showlegend=False
)

fig.update_traces(
    hovertemplate="Вес: %{y} кг"
)

st.plotly_chart(fig, use_container_width=True)


# ================= TABS =================

tab1, tab2 = st.tabs([
    "📋 Список партий",
    "📦 Дробленные партии"
])


# ================= LIST =================

with tab1:

    table = df.copy()

    drop_cols = [
        "ATA.1",
        "Batch No",
        "Remarks",
        "POD",
        "wh_ext"
    ]

    table = table.drop(
        columns=[c for c in drop_cols if c in table.columns],
        errors="ignore"
    )

    if COL_VIA and COL_FLIGHT:

        cols = table.columns.tolist()

        cols.insert(
            cols.index(COL_FLIGHT) + 1,
            cols.pop(cols.index(COL_VIA))
        )

        table = table[cols]

    table = table.reset_index(drop=True)

    table.insert(0, "№", table.index + 1)

    st.dataframe(table, use_container_width=True)


# ================= SPLIT =================

with tab2:

    if COL_SPLIT:

        split = df[df[COL_SPLIT].astype(str).str.lower() == "да"]

        rows = []

        for awb, g in split.groupby(COL_AWB):

            cartons = g[COL_CARTON].dropna().astype(int).tolist()

            if len(cartons) > 1:

                rows.append({
                    "AWB": awb,
                    "Q-ty of flights": len(cartons),
                    "Total No of cartons": sum(cartons),
                    "Q-ty of separate cartons": ", ".join(map(str, cartons))
                })

        split_table = pd.DataFrame(rows)

        if len(split_table) > 0:

            split_table.insert(0, "№", split_table.index + 1)

            st.dataframe(split_table, use_container_width=True)

        else:

            st.info("Нет дробленных партий")

    else:

        st.info("Колонка 'Дробление' не найдена")
