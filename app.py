
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re

st.set_page_config(page_title="📊 Dashboard Pro (Auto-Detect + Net/Transfer)", layout="wide")
st.title("📊 Dashboard Pro — Auto-Detect + Net/Transfer Value")

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

def safe_num(series):
    return pd.to_numeric(series, errors="coerce")

def kpi(label, value, sub=None):
    st.metric(label, value, help=sub)

# ---------- Upload ventes (single file only) ----------
uploaded_file = st.file_uploader("📂 Importer votre fichier Excel des ventes", type=["xlsx","xls"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet = st.selectbox("📑 Feuille", xls.sheet_names, index=0)
        df = pd.read_excel(uploaded_file, sheet_name=sheet)

        st.subheader("Aperçu des données")
        st.dataframe(df.head(), use_container_width=True)

        # ---------- Auto-detect targets (separate Net vs Transfer) ----------
        targets = {
            "net":      ["net transfer value","net_transfervalue","nettransfervalue","net"],
            "transfer": ["transfer value","transfervalue","transfer"],
            "vente":    ["prix vente","price","amount","total","montant","revenue","sale"],
            "date":     ["date","created time","created date","order date","orderdate","datetime","timestamp","data"],
            "status":   ["status","order status","fulfillment status","etat","state","statut","reason"],
            "qte":      ["quantity","qty","qte","sku quantity","sku qty","quantité"],
            "prix":     ["prix achat","cost","prix article","purchase price","unit cost","cost price"],
            "ship":     ["shipping fees","delivery fees","frais de livraison","livraison","shipping","delivery","fulfillment fees","frais expédition","frais transport"],
            "other":    ["cod fees","cod","commission","service fees","payment fees","frais service","frais paiement","frais commission"],
            "prod":     ["product","product name","sku","item","title","designation","article"],
            "city":     ["city","ville","locality","region"],
            "ads":      ["ads spend","ad spend","advertising","marketing","facebook ads","google ads","tiktok ads","sponsored","ad_cost","campaign spend"]
        }
        det = auto_detect(df.columns.tolist(), targets)

        # Build revenue selection priority: Net -> Transfer -> Vente
        revenue_default = det["net"] or det["transfer"] or det["vente"] or df.columns[0]
        idx_default = df.columns.get_loc(revenue_default) if revenue_default in df.columns else 0
        col_revenue = st.selectbox("🛒 Colonne des ventes (choix: Net Transfer / Transfer / ...)", df.columns, index=idx_default)
        st.caption("Astuce: choisi 'Net Transfer Value' إذا موجودة.")

        col_date  = st.selectbox("📅 Date", df.columns, index=(df.columns.get_loc(det["date"]) if det["date"] in df.columns else 0))
        col_status = st.selectbox("🏷️ Statut (optionnel)", ["(Aucune)"]+list(df.columns),
                                  index=((["(Aucune)"]+list(df.columns)).index(det["status"]) if det["status"] else 0))
        col_qte = st.selectbox("📦 Quantité (optionnel)", ["(Aucune)"]+list(df.columns),
                               index=((["(Aucune)"]+list(df.columns)).index(det["qte"]) if det["qte"] else 0))
        col_prod = st.selectbox("🧾 Produit (optionnel)", ["(Aucune)"]+list(df.columns),
                                index=((["(Aucune)"]+list(df.columns)).index(det["prod"]) if det["prod"] else 0))
        col_city = st.selectbox("📍 Ville (optionnel)", ["(Aucune)"]+list(df.columns),
                                index=((["(Aucune)"]+list(df.columns)).index(det["city"]) if det["city"] else 0))

        # Frais
        col_ship = st.selectbox("🚚 Frais Livraison (optionnel)", ["(Aucune)"]+list(df.columns),
                                index=((["(Aucune)"]+list(df.columns)).index(det["ship"]) if det["ship"] else 0))
        col_other = st.selectbox("➕ Autres Frais: COD/Commission (optionnel)", ["(Aucune)"]+list(df.columns),
                                 index=((["(Aucune)"]+list(df.columns)).index(det["other"]) if det["other"] else 0))
        ship_fixed = st.number_input("💲 Frais livraison fixe / commande (si pas de colonne)", min_value=0.0, value=0.0, step=0.1) if col_ship == "(Aucune)" else None
        other_fixed = st.number_input("💲 Autres frais fixes / commande (si pas de colonne)", min_value=0.0, value=0.0, step=0.1) if col_other == "(Aucune)" else None
        incl_fees = st.checkbox("🧮 Soustraire (Livraison + Divers) des ventes AVANT le profit", value=True)

        # Prix d'achat
        prix_source = st.radio("💰 Source du Prix d'achat", ["Colonne existante", "Prix fixe"], horizontal=True,
                               index=(0 if det["prix"] else 1))
        if prix_source == "Colonne existante":
            col_prix = st.selectbox("📄 Colonne Prix d'achat", df.columns,
                                    index=(df.columns.get_loc(det["prix"]) if det["prix"] in df.columns else 0))
        else:
            prix_fix = st.number_input("💲 Prix d'achat fixe par article", min_value=0.0, value=0.0, step=0.1)

        # Ads (simple)
        ads_mode = st.radio("📣 Dépenses Ads", ["Aucune", "Colonne dans ventes", "Montant total (période filtrée)"], horizontal=True)
        if ads_mode == "Colonne dans ventes":
            col_ads = st.selectbox("📄 Colonne Ads dans ventes", df.columns,
                                   index=(df.columns.get_loc(det["ads"]) if det["ads"] in df.columns else 0))
        elif ads_mode == "Montant total (période filtrée)":
            ads_total = st.number_input("💸 Total Ads pour la période filtrée", min_value=0.0, value=0.0, step=10.0)

        # ---------- Conversions ----------
        # Keep both Net/Transfer as columns if available (for display)
        if det["net"] in df.columns:
            df["NetTransferValue"] = safe_num(df[det["net"]])
        if det["transfer"] in df.columns:
            df["TransferValue"] = safe_num(df[det["transfer"]])

        df["VentesBrutes"] = safe_num(df[col_revenue]).fillna(0)
        df["Date"] = pd.to_datetime(df[col_date], errors="coerce")

        if col_qte == "(Aucune)":
            df["Quantité"] = 1
        else:
            df["Quantité"] = safe_num(df[col_qte]).fillna(0)

        if prix_source == "Colonne existante":
            df["PrixArticle"] = safe_num(df[col_prix]).fillna(0.0)
        else:
            df["PrixArticle"] = prix_fix

        if col_ship == "(Aucune)":
            df["FraisLivraison"] = ship_fixed if ship_fixed is not None else 0.0
        else:
            df["FraisLivraison"] = safe_num(df[col_ship]).fillna(0.0)

        if col_other == "(Aucune)":
            df["AutresFrais"] = other_fixed if other_fixed is not None else 0.0
        else:
            df["AutresFrais"] = safe_num(df[col_other]).fillna(0.0)

        # Ventes nettes (option)
        df["Ventes"] = df["VentesBrutes"] - (df["FraisLivraison"] + df["AutresFrais"]) if incl_fees else df["VentesBrutes"]

        # ---------- Filtres ----------
        # Drop rows without date to avoid chart errors
        df = df.dropna(subset=["Date"]).copy()

        min_date, max_date = df["Date"].min(), df["Date"].max()
        d_range = st.date_input("📅 Filtrer par date", [min_date, max_date])
        filt = (df["Date"].dt.date >= d_range[0]) & (df["Date"].dt.date <= d_range[1])
        filtered = df.loc[filt].copy()

        if col_status != "(Aucune)":
            vals = sorted(filtered[col_status].dropna().unique().tolist())
            chosen = st.multiselect("🏷️ Filtrer par statut", vals)
            if chosen:
                filtered = filtered[filtered[col_status].isin(chosen)]

        # Ads allocation (simple)
        filtered["AdsAllocated"] = 0.0
        if ads_mode == "Colonne dans ventes":
            filtered["AdsAllocated"] = safe_num(filtered[col_ads]).fillna(0.0)
        elif ads_mode == "Montant total (période filtrée)":
            base = filtered["VentesBrutes"].sum()
            if base > 0 and ads_total > 0:
                filtered["AdsAllocated"] = (filtered["VentesBrutes"] / base) * ads_total

        # ---------- Calculs ----------
        filtered["CoutTotal"] = filtered["PrixArticle"] * filtered["Quantité"]
        filtered["ProfitAvantAds"] = filtered["Ventes"] - filtered["CoutTotal"]
        filtered["ProfitApresAds"] = filtered["ProfitAvantAds"] - filtered["AdsAllocated"]
        filtered["Marge %"] = np.where(filtered["Ventes"]>0, (filtered["ProfitAvantAds"]/filtered["Ventes"])*100, 0)
        filtered["Marge % Après Ads"] = np.where(filtered["Ventes"]>0, (filtered["ProfitApresAds"]/filtered["Ventes"])*100, 0)

        # ---------- KPIs ----------
        c1,c2,c3,c4,c5 = st.columns(5)
        with c1: kpi("💰 Total Ventes", f"{filtered['Ventes'].sum():,.2f}")
        with c2: kpi("💵 Profit (avant Ads)", f"{filtered['ProfitAvantAds'].sum():,.2f}")
        with c3: kpi("🧮 Ads (alloc.)", f"{filtered['AdsAllocated'].sum():,.2f}")
        roas = (filtered["Ventes"].sum() / filtered["AdsAllocated"].sum()) if filtered["AdsAllocated"].sum() > 0 else np.nan
        cpo  = (filtered["AdsAllocated"].sum() / len(filtered)) if len(filtered) else np.nan
        with c4: kpi("📈 ROAS", f"{roas:,.2f}" if pd.notna(roas) else "—", "Ventes / Ads")
        with c5: kpi("🎯 CPO", f"{cpo:,.2f}" if pd.notna(cpo) else "—", "Coût / commande")

        st.markdown("---")

        # ---------- CHARTS PRO (Date fix via resample) ----------
        st.subheader("📈 Évolution — Ventes & Profits (après Ads)")
        # resample on Date to guarantee a 'Date' column (fix KeyError)
        daily = filtered.set_index("Date").resample("D").agg({
            "Ventes":"sum",
            "ProfitApresAds":"sum",
            "CoutTotal":"sum",
            "FraisLivraison":"sum",
            "AutresFrais":"sum",
            "AdsAllocated":"sum"
        }).reset_index()

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=daily["Date"], y=daily["Ventes"], mode="lines+markers", name="Ventes", line=dict(width=3)))
        fig_line.add_trace(go.Scatter(x=daily["Date"], y=daily["ProfitApresAds"], mode="lines+markers", name="Profit après Ads", line=dict(width=3)))
        fig_line.update_layout(hovermode="x unified", legend=dict(orientation="h"), margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("🧱 Décomposition quotidienne — Coûts empilés vs Ventes")
        stacked = daily.melt(id_vars=["Date"], value_vars=["CoutTotal","FraisLivraison","AutresFrais","AdsAllocated"],
                             var_name="Type", value_name="Montant")
        fig_stack = px.bar(stacked, x="Date", y="Montant", color="Type", title="COGS + Livraison + Divers + Ads (quotidien)")
        fig_stack.add_trace(go.Scatter(x=daily["Date"], y=daily["Ventes"], mode="lines", name="Ventes", line=dict(width=2)))
        fig_stack.update_layout(hovermode="x unified", legend=dict(orientation="h"), margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_stack, use_container_width=True)

        # Optionnels: Top produits / villes
        two = st.columns(2)
        if col_prod != "(Aucune)":
            prod_agg = filtered.groupby(col_prod, dropna=False).agg(Ventes=("Ventes","sum"), Profit=("ProfitApresAds","sum")).reset_index().sort_values("Ventes", ascending=False).head(10)
            two[0].plotly_chart(px.bar(prod_agg, x=col_prod, y="Ventes", hover_data=["Profit"], title="Top Produits"), use_container_width=True)
        if col_city != "(Aucune)":
            city_agg = filtered.groupby(col_city, dropna=False).agg(Ventes=("Ventes","sum"), Profit=("ProfitApresAds","sum")).reset_index().sort_values("Ventes", ascending=False).head(10)
            two[1].plotly_chart(px.bar(city_agg, x=col_city, y="Ventes", hover_data=["Profit"], title="Top Villes"), use_container_width=True)

        # ---------- Table & Export ----------
        st.subheader("📋 Données calculées (aperçu)")
        cols = ["Date","NetTransferValue","TransferValue","VentesBrutes","FraisLivraison","AutresFrais","Ventes","Quantité","PrixArticle","CoutTotal",
                "AdsAllocated","ProfitAvantAds","ProfitApresAds","Marge %","Marge % Après Ads"]
        if col_status != "(Aucune)": cols.insert(1, col_status)
        if col_prod != "(Aucune)": cols.insert(1, col_prod)
        if col_city != "(Aucune)": cols.insert(1, col_city)
        cols = [c for c in cols if c in filtered.columns or c in ["Date","VentesBrutes","FraisLivraison","AutresFrais","Ventes","Quantité","PrixArticle","CoutTotal","AdsAllocated","ProfitAvantAds","ProfitApresAds","Marge %","Marge % Après Ads","NetTransferValue","TransferValue"]]
        st.dataframe(filtered[cols].head(500), use_container_width=True)

        st.subheader("📥 Export")
        st.download_button("⬇️ Télécharger CSV (filtré)",
                           filtered.to_csv(index=False).encode("utf-8-sig"),
                           "ventes_filtrees.csv",
                           "text/csv")

    except Exception as e:
        st.error(f"Erreur: {e}")
else:
    st.info("📌 Veuillez importer un fichier Excel pour commencer.")
