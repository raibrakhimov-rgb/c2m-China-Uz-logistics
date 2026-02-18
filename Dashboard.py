# ========================================
# ФИЛЬТР ПО ПРОЕКТАМ
# ========================================

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

else:

    st.warning("Колонка 'Проект' не найдена")
