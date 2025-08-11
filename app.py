import streamlit as st
import pandas as pd
import plotly.express as px

# إعدادات الصفحة
st.set_page_config(page_title="📊 Tableau de Bord Pro - Marge", layout="wide")

st.title("📊 Tableau de Bord Professionnel - Calculateur de Marge")

# رفع ملف Excel
uploaded_file = st.file_uploader("📂 Importer votre fichier Excel", type=["xlsx", "xls"])

if uploaded_file:
    try:
        # اختيار الورقة
        xls = pd.ExcelFile(uploaded_file)
        sheet = st.selectbox("📑 Choisissez la feuille à analyser", xls.sheet_names)
        df = pd.read_excel(uploaded_file, sheet_name=sheet)

        # عرض المعاينة
        st.subheader("Aperçu des données")
        st.dataframe(df.head())

        # اختيار الأعمدة
        col_vente = st.selectbox("🛒 Colonne des ventes (Prix Vente / Net Transfer Value)", df.columns)
        col_achat = st.selectbox("💰 Colonne du prix d'achat (Coût)", df.columns)
        col_date = st.selectbox("📅 Colonne de la date", df.columns)
        col_status = st.selectbox("📦 Colonne du statut de la commande", df.columns)

        # تحويل القيم
        df["Ventes"] = pd.to_numeric(df[col_vente], errors="coerce")
        df["Cout"] = pd.to_numeric(df[col_achat], errors="coerce")
        df["Profit"] = df["Ventes"] - df["Cout"]
        df["Marge %"] = (df["Profit"] / df["Ventes"]) * 100
        df["Date"] = pd.to_datetime(df[col_date], errors="coerce")

        # فلاتر
        min_date, max_date = df["Date"].min(), df["Date"].max()
        date_range = st.date_input("📅 Filtrer par date", [min_date, max_date])
        status_filter = st.multiselect("📦 Filtrer par statut", df[col_status].unique())

        filtered_df = df.copy()
        filtered_df = filtered_df[
            (filtered_df["Date"].dt.date >= date_range[0]) &
            (filtered_df["Date"].dt.date <= date_range[1])
        ]
        if status_filter:
            filtered_df = filtered_df[filtered_df[col_status].isin(status_filter)]

        # KPIs
        total_ventes = filtered_df["Ventes"].sum()
        total_profit = filtered_df["Profit"].sum()
        marge_moy = filtered_df["Marge %"].mean()
        nb_commandes = len(filtered_df)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Total Ventes", f"{total_ventes:,.2f}")
        col2.metric("💵 Total Profit", f"{total_profit:,.2f}")
        col3.metric("📊 Marge Moyenne %", f"{marge_moy:,.2f}%")
        col4.metric("📦 Nombre de Commandes", f"{nb_commandes}")

        # Charts
        st.subheader("📈 Évolution des Ventes et Profits")
        ventes_journalieres = filtered_df.groupby(filtered_df["Date"].dt.date)["Ventes"].sum().reset_index()
        fig_ventes = px.line(ventes_journalieres, x="Date", y="Ventes", title="Ventes par Jour")
        st.plotly_chart(fig_ventes, use_container_width=True)

        profit_journalier = filtered_df.groupby(filtered_df["Date"].dt.date)["Profit"].sum().reset_index()
        fig_profit = px.line(profit_journalier, x="Date", y="Profit", title="Profits par Jour", color_discrete_sequence=["green"])
        st.plotly_chart(fig_profit, use_container_width=True)

        st.subheader("📊 Répartition des Ventes par Statut")
        ventes_par_statut = filtered_df.groupby(col_status)["Ventes"].sum().reset_index()
        fig_statut = px.pie(ventes_par_statut, names=col_status, values="Ventes", title="Répartition par Statut")
        st.plotly_chart(fig_statut, use_container_width=True)

        # Télécharger النتائج
        st.subheader("📥 Télécharger les Données Filtrées")
        csv_data = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ Télécharger en CSV", csv_data, "ventes_filtrees.csv", "text/csv")

    except Exception as e:
        st.error(f"Erreur: {e}")
else:
    st.info("📌 Veuillez importer un fichier Excel pour commencer.")
