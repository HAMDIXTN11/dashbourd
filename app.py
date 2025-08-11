import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Calculateur de Marge", layout="wide")

st.title("📊 Calculateur de Marge avec Dashboard")

uploaded_file = st.file_uploader("📂 Importer votre fichier Excel", type=["xlsx", "xls"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet = st.selectbox("📑 Choisissez la feuille à analyser", xls.sheet_names)
        df = pd.read_excel(uploaded_file, sheet_name=sheet)

        st.subheader("Aperçu des données")
        st.dataframe(df.head())

        col_vente = st.selectbox("🛒 Colonne des ventes (Prix Vente / Net Transfer Value)", df.columns)
        col_achat = st.selectbox("💰 Colonne du prix d'achat (Coût)", df.columns)
        col_date = st.selectbox("📅 Colonne de la date", df.columns)

        df["Ventes"] = pd.to_numeric(df[col_vente], errors="coerce")
        df["Cout"] = pd.to_numeric(df[col_achat], errors="coerce")
        df["Profit"] = df["Ventes"] - df["Cout"]
        df["Marge %"] = (df["Profit"] / df["Ventes"]) * 100
        df["Date"] = pd.to_datetime(df[col_date], errors="coerce")

        total_ventes = df["Ventes"].sum()
        total_profit = df["Profit"].sum()
        marge_moy = df["Marge %"].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Ventes", f"{total_ventes:,.2f}")
        col2.metric("💵 Total Profit", f"{total_profit:,.2f}")
        col3.metric("📊 Marge Moyenne %", f"{marge_moy:,.2f}%")

        ventes_journalieres = df.groupby(df["Date"].dt.date)["Ventes"].sum().reset_index()
        fig_ventes = px.line(ventes_journalieres, x="Date", y="Ventes", title="📈 Évolution des ventes")
        st.plotly_chart(fig_ventes, use_container_width=True)

        profit_journalier = df.groupby(df["Date"].dt.date)["Profit"].sum().reset_index()
        fig_profit = px.line(profit_journalier, x="Date", y="Profit", title="💵 Évolution du profit", color_discrete_sequence=["green"])
        st.plotly_chart(fig_profit, use_container_width=True)

    except Exception as e:
        st.error(f"Erreur: {e}")
else:
    st.info("📌 Veuillez importer un fichier Excel pour commencer.")
