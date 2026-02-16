import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

st.set_page_config(
    page_title="China → Uzbekistan Logistics",
    layout="wide"
)

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
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
    df.columns = df.columns.astype(str).str.strip()

    # только данные с 867 строки
    df = df.iloc[866:].reset_index(drop=True)

    return df

df = load_data()

# ================= FIND COLUMNS =================

def find_col(keys):

    for col in df.columns:

        name = col.lower()

        for k in keys:
            if k in name:
                return col

    return None


COL_WEIGHT = find_col(["weight", "kg"])
COL_CARTON = find_col(["carton"])
COL_DATE = find_col(["outbound date"])
COL_ETD = find_col(["etd"])
COL_ETA = find_col(["eta"])
COL_ATD = find_col(["atd"])
COL_ATA = find_col(["ata"])
COL_AWB = find_col(["awb"])
COL_PROJECT = find_col(["project", "проект"])
COL_SPLIT = find_col(["дроб"])

REQUIRED = [
    COL_WEIGHT,
    COL_CARTON,
    COL_DATE,
    COL_AWB,
    COL_PROJECT
]

if any(x is None for x in REQUIRED):

    st.error("Не найдены обязательные колонки")
    st.write(df.columns)
    st.stop()

# ================= TYPE CONVERSION =================

df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")
df[COL_CARTON] = pd.to_numeric(df[COL_CARTON], errors="coerce")
df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce")

for c in [COL_ETD, COL_ETA, COL_ATD, COL_ATA]:

    if c:
        df[c] = pd.to_datetime(df[c], errors="coerce")

df = df.dropna(subset=[COL_DATE])

# ================= TITLE =================

st.title("✈️ Сводная по вылетам из Китая в Узбекистан")

# ================= FILTER =================

projects = ["Все"] + sorted(df[COL_PROJECT].dropna().unique())

project = st.radio(
    "Проект:",
    projects,
    horizontal=True
)

if project != "Все":
    df = df[df[COL_PROJECT] == project]

# ================= KPI =================

total_flights = df[COL_AWB].nunique()
total_weight = int(df[COL_WEIGHT].sum())
total_cartons = int(df[COL_CARTON].sum())
avg_weight = int(df[COL_WEIGHT].mean())

col1, col2, col3, col4 = st.columns(4)

col1.metric("Количество рейсов", total_flights)
col2.metric("Общий вес (кг)", f"{total_weight:,}")
col3.metric("Количество коробов", f"{total_cartons:,}")
col4.metric("Средний вес рейса (кг)", f"{avg_weight:,}")

# ================= GROUP SELECT =================

group = st.radio(
    "Период:",
    ["По дням", "По неделям", "По месяцам"],
    horizontal=True
)

chart_df = df.copy()

# ================= GROUPING =================

if group == "По дням":

    chart_df["period"] = chart_df[COL_DATE].dt.date
    chart_df["label"] = chart_df[COL_DATE].dt.strftime("%d.%m")

elif group == "По неделям":

    chart_df["start"] = chart_df[COL_DATE] - pd.to_timedelta(
        chart_df[COL_DATE].dt.weekday, unit="D"
    )

    chart_df["period"] = chart_df["start"]

    chart_df["label"] = (
        chart_df["start"].dt.strftime("%d.%m")
        + "-"
        + (chart_df["start"] + pd.Timedelta(days=6)).dt.strftime("%d.%m")
    )

else:

    months = {
        1:"январь",2:"февраль",3:"март",
        4:"апрель",5:"май",6:"июнь",
        7:"июль",8:"август",9:"сентябрь",
        10:"октябрь",11:"ноябрь",12:"декабрь"
    }

    chart_df["period"] = chart_df[COL_DATE].dt.to_period("M")

    chart_df["label"] = (
        chart_df[COL_DATE].dt.month.map(months)
        + " "
        + chart_df[COL_DATE].dt.year.astype(str)
    )

# ================= AGGREGATE =================

grouped = (
    chart_df
    .groupby(["period","label"])
    [COL_WEIGHT]
    .sum()
    .reset_index()
    .sort_values("period")
)

# ================= CHART =================

fig = px.bar(
    grouped,
    x="label",
    y=COL_WEIGHT,
    text=COL_WEIGHT,
    hover_data={"label":True, COL_WEIGHT:True},
)

fig.update_layout(
    height=500,
    xaxis_title="",
    yaxis_title="Вес (кг)",
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

    remove_cols = [
        "Batch No",
        "Дней до прибытия",
        "Поступления",
        "wh_ext",
        "POD",
        "Remarks"
    ]

    for col in remove_cols:

        for c in table.columns:

            if col.lower() in c.lower():
                table = table.drop(columns=[c])

    table = table.sort_values(COL_DATE, ascending=False)
    table = table.reset_index(drop=True)

    table.insert(0, "№", range(1, len(table)+1))

    st.dataframe(table, use_container_width=True)

# ================= SPLIT =================

with tab2:

    if not COL_SPLIT:

        st.info("Нет данных")

    else:

        split = df[df[COL_SPLIT].astype(str).str.lower()=="да"]

        rows=[]

        for awb,g in split.groupby(COL_AWB):

            cartons=g[COL_CARTON].dropna().astype(int).tolist()

            if len(cartons)<2:
                continue

            rows.append({

                "AWB":awb,
                "Q-ty of flights":len(cartons),
                "Total No of cartons":sum(cartons),
                "Q-ty of separate cartons":", ".join(map(str,cartons))
            })

        if rows:

            split_table=pd.DataFrame(rows)
            split_table.insert(0,"№",range(1,len(split_table)+1))
            st.dataframe(split_table,use_container_width=True)

        else:

            st.info("Нет дробленных партий")
