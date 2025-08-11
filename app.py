import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="📊 Dashboard Pro (Auto-Detect + Frais)", layout="wide")
st.title("📊 Tableau de Bord Pro — Auto-Detect + Livraison/Frais")

# ---------- Helpers ----------
def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def auto_detect(columns, targets):
    norm_map = {c: norm(c) for c in columns}
    result = {}
    for key, cand_list in targets.items():
        best = None
        for c in columns:
            nc = norm_map[c]
            if any(nc.find(norm(alias)) >= 0 for alias in cand_list):
                best = c
                break
        result[key] = best
    return result

uploaded_file = st.file_uploader("📂 Importer votre fichier Excel", type=["xlsx","xls"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet = st.selectbox("📑 Feuille", xls.sheet_names, index=0)
        df = pd.read_excel(uploaded_file, sheet_name=sheet)

        st.subheader("Aperçu des données")
        st.dataframe(df.head())

        # ---------- Auto detect ----------
        targets = {
            "vente": [
                "net transfer value","net_transfervalue","nettransfervalue",
                "transfer value","transfervalue","prix vente","price","amount","total","montant"
            ],
            "date": ["date","created time","created date","order date","orderdate","datetime","timestamp","data"],
            "status": ["status","order status","fulfillment status","etat","state","statut","reason"],
            "qte": ["quantity","qty","qte","sku quantity","sku qty","quantité"],
            "prix_article": ["prix achat","cost","prix article","purchase price","unit cost","cost price"],
            # NEW: shipping/delivery fees
            "livraison": [
                "shipping fees","delivery fees","frais de livraison","livraison",
                "shipping","delivery","fulfillment fees","frais expédition","frais transport"
            ],
            # NEW: other fees (COD/commission/service)
            "autres": [
                "cod fees","cod","commission","service fees","payment fees",
                "frais service","frais paiement","frais commission"
            ],
            "ville": ["city","ville","locality","region"],
            "produit": ["product","product name","sku","item","title","designation","article"]
        }
        detected = auto_detect(df.columns.tolist(), targets)

        # ---------- Mapping de base ----------
        col_vente = st.selectbox("🛒 Ventes (Net/Transfer Value)", df.columns,
                                 index=(df.columns.get_loc(detected["vente"]) if detected["vente"] in df.columns else 0))
        col_date  = st.selectbox("📅 Date", df.columns,
                                 index=(df.columns.get_loc(detected["date"]) if detected["date"] in df.columns else 0))
        col_status = st.selectbox("🏷️ Statut (optionnel)", ["(Aucune)"]+list(df.columns),
                                  index=( (["(Aucune)"]+list(df.columns)).index(detected["status"]) if detected["status"] else 0))
        col_qte = st.selectbox("📦 Quantité (optionnel)", ["(Aucune)"]+list(df.columns),
                               index=( (["(Aucune)"]+list(df.columns)).index(detected["qte"]) if detected["qte"] else 0))
        col_prix_article_opt = st.selectbox("💰 Prix d'achat (optionnel)", ["--Entrer manuellement--"]+list(df.columns),
                               index=( (["--Entrer manuellement--"]+list(df.columns)).index(detected["prix_article"]) if detected["prix_article"] else 0))

        # ---------- Mapping des frais ----------
        col_shipping = st.selectbox("🚚 Frais de livraison (optionnel)", ["(Aucune)"]+list(df.columns),
                                    index=( (["(Aucune)"]+list(df.columns)).index(detected["livraison"]) if detected["livraison"] else 0))
        col_autres   = st.selectbox("➕ Autres frais: COD / Commission (optionnel)", ["(Aucune)"]+list(df.columns),
                                    index=( (["(Aucune)"]+list(df.columns)).index(detected["autres"]) if detected["autres"] else 0))

        # Valeurs par défaut si لا توجد أعمدة
        shipping_fixe = None
        autres_fixe   = None
        if col_shipping == "(Aucune)":
            shipping_fixe = st.number_input("💲 Frais livraison fixe / commande (si pas de colonne)", min_value=0.0, value=0.0, step=0.1)
        if col_autres == "(Aucune)":
            autres_fixe = st.number_input("💲 Autres frais fixes / commande (si pas de colonne)", min_value=0.0, value=0.0, step=0.1)

        # Option: احتساب المصاريف قبل/بعد المبيعات (عادة قبل الربح)
        incl_fees = st.checkbox("🧮 Soustraire livraison + autres frais des ventes AVANT calcul du profit", value=True)

        # Colonnes اختيارية Produit/ Ville
        opt_cols = ["(Aucune)"] + list(df.columns)
        col_product = st.selectbox("🧾 Produit (optionnel)", opt_cols, index=(opt_cols.index(detected["produit"]) if detected["produit"] else 0))
        col_city    = st.selectbox("📍 Ville (optionnel)", opt_cols, index=(opt_cols.index(detected["ville"]) if detected["ville"] else 0))

        # ---------- Calculs ----------
        df["VentesBrutes"] = pd.to_numeric(df[col_vente], errors="coerce").fillna(0)

        # Quantité
        if col_qte == "(Aucune)":
            df["Quantité"] = 1
        else:
            df["Quantité"] = pd.to_numeric(df[col_qte], errors="coerce").fillna(0)

        # Prix Article
        if col_prix_article_opt == "--Entrer manuellement--":
            prix_article_fixe = st.number_input("💲 Prix d'achat fixe par article", min_value=0.0, value=0.0, step=0.1)
            df["PrixArticle"] = prix_article_fixe
        else:
            df["PrixArticle"] = pd.to_numeric(df[col_prix_article_opt], errors="coerce").fillna(0)

        # Frais livraison
        if col_shipping == "(Aucune)":
            df["FraisLivraison"] = shipping_fixe if shipping_fixe is not None else 0.0
        else:
            df["FraisLivraison"] = pd.to_numeric(df[col_shipping], errors="coerce").fillna(0)

        # Autres frais
        if col_autres == "(Aucune)":
            df["AutresFrais"] = autres_fixe if autres_fixe is not None else 0.0
        else:
            df["AutresFrais"] = pd.to_numeric(df[col_autres], errors="coerce").fillna(0)

        # Coût total marchandise
        df["CoutTotal"] = df["PrixArticle"] * df["Quantité"]

        # Ventes nettes (قبل الربح) إذا مفعل
        if incl_fees:
            df["Ventes"] = df["VentesBrutes"] - (df["FraisLivraison"] + df["AutresFrais"])
        else:
            df["Ventes"] = df["VentesBrutes"]

        # Profit & Marge
        df["Profit"]  = df["Ventes"] - df["CoutTotal"]
        df["Marge %"] = (df["Profit"] / df["Ventes"]).replace([pd.NA, pd.NaT], 0) * 100

        # Date
        df["Date"] = pd.to_datetime(df[col_date], errors="coerce")

        # ---------- Filtres ----------
        min_date, max_date = df["Date"].min(), df["Date"].max()
        date_range = st.date_input("📅 Filtrer par date", [min_date, max_date])

        filtered = df[(df["Date"].dt.date >= date_range[0]) & (df["Date"].dt.date <= date_range[1])].copy()

        if col_status != "(Aucune)":
            vals = sorted(filtered[col_status].dropna().unique().tolist())
            chosen = st.multiselect("🏷️ Filtrer par statut", vals)
            if chosen:
                filtered = filtered[filtered[col_status].isin(chosen)]

        # ---------- KPIs ----------
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("💰 Total Ventes", f"{filtered['Ventes'].sum():,.2f}")
        c2.metric("💵 Total Profit", f"{filtered['Profit'].sum():,.2f}")
        c3.metric("📊 Marge Moyenne %", f"{filtered['Marge %'].mean():,.2f}%")
        c4.metric("📦 Nombre de Commandes", f"{len(filtered)}")

        # ---------- Charts ----------
        st.subheader("⏱️ Évolution")
        by_day_sales  = filtered.groupby(filtered["Date"].dt.date)["Ventes"].sum().reset_index()
        by_day_profit = filtered.groupby(filtered["Date"].dt.date)["Profit"].sum().reset_index()
        st.plotly_chart(px.line(by_day_sales,  x="Date", y="Ventes", title="Ventes / Jour"), use_container_width=True)
        st.plotly_chart(px.line(by_day_profit, x="Date", y="Profit", title="Profits / Jour"), use_container_width=True)

        st.subheader("🏷️ Répartition des Ventes par Statut")
        if col_status != "(Aucune)":
            pie_df = filtered.groupby(col_status, dropna=False)["Ventes"].sum().reset_index()
            st.plotly_chart(px.pie(pie_df, names=col_status, values="Ventes", title="Ventes par Statut"), use_container_width=True)
        else:
            st.info("Aucune colonne Statut sélectionnée.")

        # Produits & Villes
        two = st.columns(2)
        if col_product != "(Aucune)":
            prod = filtered.groupby(col_product, dropna=False).agg(Ventes=("Ventes","sum"), Profit=("Profit","sum")).reset_index().sort_values("Ventes", ascending=False).head(10)
            two[0].plotly_chart(px.bar(prod, x=col_product, y="Ventes", hover_data=["Profit"], title="Top Produits"), use_container_width=True)
        if col_city != "(Aucune)":
            city = filtered.groupby(col_city, dropna=False).agg(Ventes=("Ventes","sum"), Profit=("Profit","sum")).reset_index().sort_values("Ventes", ascending=False).head(10)
            two[1].plotly_chart(px.bar(city, x=col_city, y="Ventes", hover_data=["Profit"], title="Top Villes"), use_container_width=True)

        # ---------- Table & Export ----------
        st.subheader("📋 Données calculées (aperçu)")
        base_cols = ["Date","VentesBrutes","FraisLivraison","AutresFrais","Ventes","Quantité","PrixArticle","CoutTotal","Profit","Marge %"]
        opt_cols  = []
        if col_status  != "(Aucune)": opt_cols.append(col_status)
        if col_product != "(Aucune)": opt_cols.append(col_product)
        if col_city    != "(Aucune)": opt_cols.append(col_city)
        show_cols = ["Date"] + opt_cols + [c for c in base_cols if c!="Date"]
        show_cols = [c for c in show_cols if c in filtered.columns or c in base_cols]
        st.dataframe(filtered[show_cols].head(200))

        st.subheader("📥 Export")
        st.download_button("⬇️ Télécharger CSV (filtré)", filtered.to_csv(index=False).encode("utf-8-sig"),
                           "ventes_filtrees.csv", "text/csv")

    except Exception as e:
        st.error(f"Erreur: {e}")
else:
    st.info("📌 Veuillez importer un fichier Excel pour commencer.")
