import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

# ============================================
# CONFIG
# ============================================

st.set_page_config(
    page_title="Логистика Китай → Узбекистан",
    layout="wide"
)

st.title("✈️ Сводная по вылетам Китай → Узбекистан")

SHEET_ID = "1HeNTJS3lCHr37K3TmgeCzQwt2i9n5unA"
GID = "1730191747"

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# ============================================
# LOAD DATA
# ============================================

@st.cache_data(ttl=300)
def load_data():

    r = requests.get(URL)
    r.raise_for_status()

    df = pd.read_excel(
        BytesIO(r.content),
        engine="openpyxl",
        header=1
    )

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    df.columns = df.columns.astype(str).str.strip()

    # данные с 2026
    df = df.iloc[866:].copy()

    df.reset_index(drop=True, inplace=True)

    return df


df = load_data()

# ============================================
# CLEAN TYPES
# ============================================

def to_date(col):

    if col in df.columns:

        df[col] = pd.to_datetime(
            df[col],
            errors="coerce"
        ).dt.date


def to_numeric(col):

    if col in df.columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


to_numeric("Outbound weight (kg)")
to_numeric("Outbound carton")

to_date("Outbound date")
to_date("ETD")
to_date("ATD")
to_date("ETA")
to_date("ATA")

# ============================================
# PROJECT FILTER
# ============================================

if "Проект" in df.columns:

    projects = ["Все"] + sorted(
        df["Проект"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_project = st.radio(
        "Проект:",
        projects,
        horizontal=True
    )

    if selected_project != "Все":

        df = df[
            df["Проект"].astype(str)
            == selected_project
        ]

# ============================================
# KPI
# ============================================

total_weight = int(df["Outbound weight (kg)"].sum())

total_flights = df["Booking/AWB NO"].nunique()

avg_weight = int(
    df["Outbound weight (kg)"].mean()
)

transit = None

if "ETD" in df.columns and "ATA" in df.columns:

    temp = df.dropna(
        subset=["ETD", "ATA"]
    ).copy()

    temp["transit"] = (
        pd.to_datetime(temp["ATA"])
        -
        pd.to_datetime(temp["ETD"])
    ).dt.days

    temp = temp[
        (temp["transit"] >= 0)
        &
        (temp["transit"] <= 15)
    ]

    if len(temp) > 0:

        transit = round(
            temp["transit"].mean(),
            1
        )

# KPI display

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Общий вес",
    f"{total_weight:,} кг"
)

col2.metric(
    "Количество рейсов",
    total_flights
)

col3.metric(
    "Средний вес",
    f"{avg_weight} кг"
)

col4.metric(
    "Средний transit time",
    f"{transit} дней" if transit else "-"
)

# ============================================
# PERIOD SELECT
# ============================================

period = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

if period == "По дням":

    grouped = chart_df.groupby(
        "Outbound date"
    )["Outbound weight (kg)"].sum().reset_index()

    grouped = grouped.sort_values(
        "Outbound date"
    )

    grouped["label"] = grouped["Outbound date"].astype(str)

elif period == "По неделям":

    chart_df["week"] = pd.to_datetime(
        chart_df["Outbound date"]
    ).dt.to_period("W").astype(str)

    grouped = chart_df.groupby(
        "week"
    )["Outbound weight (kg)"].sum().reset_index()

    grouped["label"] = grouped["week"]

else:

    chart_df["month"] = pd.to_datetime(
        chart_df["Outbound date"]
    ).dt.to_period("M").astype(str)

    grouped = chart_df.groupby(
        "month"
    )["Outbound weight (kg)"].sum().reset_index()

    grouped["label"] = grouped["month"]

# ============================================
# CHART
# ============================================

fig = px.bar(

    grouped,

    x="Outbound weight (kg)",

    y="label",

    orientation="h",

    text="Outbound weight (kg)",

    height=700
)

fig.update_traces(

    textposition="inside",

    insidetextanchor="middle",

    textangle=0
)

fig.update_layout(

    yaxis_title="",

    xaxis_title="Вес (кг)",

    showlegend=False
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ============================================
# TABS
# ============================================

tab1, tab2 = st.tabs(
    ["Список партий", "Дробленные партии"]
)

# ============================================
# SHIPMENTS TABLE
# ============================================

with tab1:

    table = df.copy()

    if "ATA_ext" in table.columns:

        table.rename(
            columns={
                "ATA_ext": "ATA_time"
            },
            inplace=True
        )

    if "№" in table.columns:

        table.drop(
            columns=["№"],
            inplace=True
        )

    table.insert(
        0,
        "№",
        range(
            1,
            len(table)+1
        )
    )

    drop_cols = [

        "Batch No",
        "ATA.1",
        "Комментарий",
        "Comments"
    ]

    table = table.drop(
        columns=[
            c for c in drop_cols
            if c in table.columns
        ],
        errors="ignore"
    )

    st.dataframe(
        table,
        use_container_width=True
    )

# ============================================
# SPLIT SHIPMENTS
# ============================================

with tab2:

    if "Дробление" in df.columns:

        split = df[
            df["Дробление"].astype(str).str.lower()
            == "да"
        ]

        rows = []

        for awb, g in split.groupby(
            "Booking/AWB NO"
        ):

            cartons = g[
                "Outbound carton"
            ].dropna().astype(int)

            ata = g["ATA"].max()

            rows.append({

                "AWB": awb,

                "Количество рейсов": len(g),

                "Общее кол-во коробок": cartons.sum(),

                "Разделено на": ", ".join(
                    cartons.astype(str)
                ),

                "ATA (при дроблении)": ata

            })

        if len(rows) > 0:

            split_table = pd.DataFrame(rows)

            split_table.insert(
                0,
                "№",
                range(
                    1,
                    len(split_table)+1
                )
            )

            st.dataframe(
                split_table,
                use_container_width=True
            )

        else:

            st.info(
                "Нет дробленных партий"
            )
