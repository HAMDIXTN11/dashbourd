
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
from pathlib import Path

# ---------- Branding / Theme ----------
# Try to set page icon to brand logo if present
logo_candidates = ["assets/logo_corella.png", "logo_corella.png"]
page_icon = None
for p in logo_candidates:
    if Path(p).exists():
        page_icon = p
        break

st.set_page_config(
    page_title="Corella Store — Dashboard Pro",
    layout="wide",
    page_icon=page_icon
)

# Global Plotly dark theme + brand palette
px.defaults.template = "plotly_dark"
BRAND_GOLD = "#D4AF37"
PALETTE = [BRAND_GOLD, "#2DD4BF", "#60A5FA", "#F43F5E", "#A78BFA", "#34D399", "#F59E0B"]
px.defaults.color_discrete_sequence = PALETTE

# Top header with logo on dark background
left, mid, right = st.columns([1,3,1])
with left:
    if page_icon:
        st.image(page_icon, width=140)
with mid:
    st.markdown("<h1 style='text-align:center;margin-bottom:0'>Corella Store — Dashboard Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#c9d1d9'>Ventes, marges, frais & ads dans un seul tableau de bord.</p>", unsafe_allow_html=True)

st.markdown("---")

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

def kpi(label:str, value:str, sub:str=""):
    st.markdown(f"""
    <div style="background:#111418;border:1px solid #1f2937;border-radius:14px;padding:16px">
        <div style="color:#9CA3AF;font-size:13px">{label}</div>
        <div style="font-weight:700;font-size:22px;color:#F9FAFB;margin-top:2px">{value}</div>
        {'<div style="color:#6B7280;font-size:12px;margin-top:2px">'+sub+'</div>' if sub else ''}
    </div>
    """, unsafe_allow_html=True)

def safe_num(x):
    try:
        return pd.to_numeric(x, errors="coerce")
    except Exception:
        return pd.Series([np.nan]*len(x))

# ---------- Upload ventes ----------
uploaded_file = st.file_uploader("📂 Importer votre fichier Excel des ventes", type=["xlsx","xls"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet = st.selectbox("📑 Feuille des ventes", xls.sheet_names, index=0)
        df = pd.read_excel(uploaded_file, sheet_name=sheet)

        st.subheader("Aperçu des données (ventes)")
        st.dataframe(df.head(), use_container_width=True)

        # ---------- Auto detect ventes ----------
        targets = {
            "vente": [
                "net transfer value","net_transfervalue","nettransfervalue",
                "transfer value","transfervalue","prix vente","price","amount","total","montant","revenue","sale"
            ],
            "date": ["date","created time","created date","order date","orderdate","datetime","timestamp","data"],
            "status": ["status","order status","fulfillment status","etat","state","statut","reason"],
            "qte": ["quantity","qty","qte","sku quantity","sku qty","quantité"],
            "prix_article": ["prix achat","cost","prix article","purchase price","unit cost","cost price"],
            "livraison": [
                "shipping fees","delivery fees","frais de livraison","livraison",
                "shipping","delivery","fulfillment fees","frais expédition","frais transport"
            ],
            "autres": [
                "cod fees","cod","commission","service fees","payment fees",
                "frais service","frais paiement","frais commission"
            ],
            "ads": ["ads spend","ad spend","advertising","marketing","facebook ads","google ads","tiktok ads","sponsored","sponsorisée","sponsore","ad_cost","campaign spend"],
            "ville": ["city","ville","locality","region"],
            "produit": ["product","product name","sku","item","title","designation","article"]
        }
        detected = auto_detect(df.columns.tolist(), targets)

        # ---------- Mapping de base ----------
        with st.expander("🔧 Mapping des colonnes ventes", expanded=True):
            col_vente = st.selectbox("🛒 Ventes (Net/Transfer Value)", df.columns,
                                    index=(df.columns.get_loc(detected["vente"]) if detected["vente"] in df.columns else 0))
            col_date  = st.selectbox("📅 Date", df.columns,
                                    index=(df.columns.get_loc(detected["date"]) if detected["date"] in df.columns else 0))
            col_status = st.selectbox("🏷️ Statut (optionnel)", ["(Aucune)"]+list(df.columns),
                                    index=( (["(Aucune)"]+list(df.columns)).index(detected["status"]) if detected["status"] else 0))
            col_qte = st.selectbox("📦 Quantité (optionnel)", ["(Aucune)"]+list(df.columns),
                                index=( (["(Aucune)"]+list(df.columns)).index(detected["qte"]) if detected["qte"] else 0))
            prod_opts = ["(Aucune)"] + list(df.columns)
            col_product = st.selectbox("🧾 Produit (pour coûts par produit)", prod_opts,
                                    index=(prod_opts.index(detected["produit"]) if detected["produit"] else 0))
            col_city    = st.selectbox("📍 Ville (optionnel)", prod_opts,
                                    index=(prod_opts.index(detected["ville"]) if detected["ville"] else 0))

        # ---------- Frais ----------
        with st.expander("🚚 Frais logistiques & divers"):
            col_shipping = st.selectbox("🚚 Frais de livraison (optionnel)", ["(Aucune)"]+list(df.columns),
                                        index=( (["(Aucune)"]+list(df.columns)).index(detected["livraison"]) if detected["livraison"] else 0))
            col_autres   = st.selectbox("➕ Autres frais: COD / Commission (optionnel)", ["(Aucune)"]+list(df.columns),
                                        index=( (["(Aucune)"]+list(df.columns)).index(detected["autres"]) if detected["autres"] else 0))
            shipping_fixe = None
            autres_fixe   = None
            if col_shipping == "(Aucune)":
                shipping_fixe = st.number_input("💲 Frais livraison fixe / commande (si pas de colonne)", min_value=0.0, value=0.0, step=0.1)
            if col_autres == "(Aucune)":
                autres_fixe = st.number_input("💲 Autres frais fixes / commande (si pas de colonne)", min_value=0.0, value=0.0, step=0.1)
            incl_fees = st.checkbox("🧮 Soustraire livraison + autres frais des ventes AVANT calcul du profit", value=True)

        # ---------- Prix d'achat (COGS) ----------
        with st.expander("💰 Coût d'achat (COGS) — choisissez la source", expanded=True):
            source_prix = st.radio("Source du Prix d'achat", ["Colonne existante", "Prix fixe", "Par produit (table)"], horizontal=True)
            if source_prix == "Colonne existante":
                col_prix_article_opt = st.selectbox("📄 Colonne du prix d'achat", df.columns)
            elif source_prix == "Prix fixe":
                prix_article_fixe = st.number_input("💲 Prix d'achat fixe par article", min_value=0.0, value=0.0, step=0.1)
            else:
                if col_product == "(Aucune)":
                    st.error("🔴 Sélectionnez une colonne Produit pour utiliser la table de coûts par produit.")
                    st.stop()
                st.markdown("**Option A :** Importer un fichier coûts (CSV/XLSX) avec colonnes *Produit* et *PrixArticle*.")
                cost_file = st.file_uploader("📥 Importer table de coûts (optionnel)", type=["csv","xlsx","xls"], key="costs")
                cost_map_df = None
                if cost_file is not None:
                    if cost_file.name.lower().endswith(".csv"):
                        cost_df = pd.read_csv(cost_file)
                    else:
                        cxls = pd.ExcelFile(cost_file)
                        csheet = st.selectbox("📑 Feuille des coûts", cxls.sheet_names, index=0)
                        cost_df = pd.read_excel(cost_file, sheet_name=csheet)
                    # détecter colonnes
                    def _auto(cols, t):
                        nm = {c: re.sub(r"[^a-z0-9]","", c.lower()) for c in cols}
                        res = {}
                        for k, lst in t.items():
                            res[k] = next((c for c in cols if any(nm[c].find(re.sub(r"[^a-z0-9]","", a.lower()))>=0 for a in lst)), None)
                        return res
                    det2 = _auto(cost_df.columns.tolist(), {
                        "prod": ["product","produit","sku","item","title","designation","article"],
                        "cost": ["prix achat","cost","prix article","purchase price","unit cost","cost price"]
                    })
                    prod_col2 = st.selectbox("🧾 Colonne Produit (fichier coûts)", cost_df.columns,
                                            index=(cost_df.columns.get_loc(det2["prod"]) if det2["prod"] in cost_df.columns else 0))
                    cost_col2 = st.selectbox("💰 Colonne Prix d'achat (fichier coûts)", cost_df.columns,
                                            index=(cost_df.columns.get_loc(det2["cost"]) if det2["cost"] in cost_df.columns else 0))
                    cost_map_df = cost_df[[prod_col2, cost_col2]].rename(columns={prod_col2:"Produit", cost_col2:"PrixArticle"})
                    cost_map_df["Produit"] = cost_map_df["Produit"].astype(str)
                    cost_map_df["PrixArticle"] = pd.to_numeric(cost_map_df["PrixArticle"], errors="coerce")
                st.markdown("**Option B :** Éditer manuellement ci-dessous.")
                unique_prods = pd.DataFrame({"Produit": sorted(df[col_product].dropna().astype(str).unique().tolist())})
                if "cost_editor_df" not in st.session_state:
                    st.session_state.cost_editor_df = unique_prods
                    if cost_map_df is not None:
                        st.session_state.cost_editor_df = unique_prods.merge(cost_map_df, on="Produit", how="left")
                else:
                    st.session_state.cost_editor_df = unique_prods.merge(st.session_state.cost_editor_df, on="Produit", how="left")
                edited = st.data_editor(
                    st.session_state.cost_editor_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="cost_editor_table",
                    column_config={
                        "Produit": st.column_config.TextColumn(disabled=True),
                        "PrixArticle": st.column_config.NumberColumn("PrixArticle", step=0.1, format="%.3f")
                    }
                )
                st.session_state.cost_editor_df = edited
                st.download_button("⬇️ Télécharger la table de coûts (CSV)",
                                st.session_state.cost_editor_df.to_csv(index=False).encode("utf-8-sig"),
                                "table_couts_produits.csv", "text/csv")

        # ---------- Ads Spend ----------
        with st.expander("📣 Dépenses publicitaires (Ads) — ROAS / CPO", expanded=True):
            ads_source = st.radio("Source des dépenses Ads", ["Aucune", "Colonne dans ventes", "Fichier Ads séparé", "Montant total (période filtrée)"], horizontal=True)
            ads_alloc_mode = st.selectbox("Méthode d'allocation des Ads", ["par commande (count)", "par ventes (montant)"], index=1)

            col_ads_in_sales = None
            ads_total_manual = 0.0
            ads_df = None

            if ads_source == "Colonne dans ventes":
                default_ads_col = detected["ads"] if detected["ads"] in df.columns else df.columns[0]
                col_ads_in_sales = st.selectbox("📄 Colonne Ads dans le fichier ventes", df.columns, index=df.columns.get_loc(default_ads_col) if default_ads_col in df.columns else 0)
            elif ads_source == "Fichier Ads séparé":
                st.markdown("Chargez un fichier (CSV/XLSX) avec colonnes Date, Spend et (optionnel) Channel.")
                f = st.file_uploader("📥 Importer fichier Ads", type=["csv","xlsx","xls"], key="ads_file")
                if f is not None:
                    if f.name.lower().endswith(".csv"):
                        ads_df = pd.read_csv(f)
                    else:
                        axls = pd.ExcelFile(f)
                        asheet = st.selectbox("📑 Feuille Ads", axls.sheet_names, index=0)
                        ads_df = pd.read_excel(f, sheet_name=asheet)
                    def _auto2(cols, t):
                        nm = {c: re.sub(r"[^a-z0-9]","", c.lower()) for c in cols}
                        res = {}
                        for k, lst in t.items():
                            res[k] = next((c for c in cols if any(nm[c].find(re.sub(r"[^a-z0-9]","", a.lower()))>=0 for a in lst)), None)
                        return res
                    det_ads = _auto2(ads_df.columns.tolist(), {
                        "date": ["date","day","jour","datetime","timestamp"],
                        "spend": ["spend","ads spend","ad spend","cost","montant","dépense","budget"],
                        "channel": ["channel","campaign","source","réseau","reseau","plateforme"]
                    })
                    col_ads_date = st.selectbox("📅 Colonne Date (Ads)", ads_df.columns, index=(ads_df.columns.get_loc(det_ads["date"]) if det_ads["date"] in ads_df.columns else 0))
                    col_ads_spend = st.selectbox("💸 Colonne Spend", ads_df.columns, index=(ads_df.columns.get_loc(det_ads["spend"]) if det_ads["spend"] in ads_df.columns else 0))
                    col_ads_channel = st.selectbox("📡 Colonne Channel (optionnelle)", ["(Aucune)"]+list(ads_df.columns),
                                                   index=( (["(Aucune)"]+list(ads_df.columns)).index(det_ads["channel"]) if det_ads["channel"] else 0))
                    ads_df = ads_df.rename(columns={col_ads_date:"AdsDate", col_ads_spend:"AdsSpend"})
                    if col_ads_channel != "(Aucune)":
                        ads_df = ads_df.rename(columns={col_ads_channel:"AdsChannel"})
                    ads_df["AdsDate"] = pd.to_datetime(ads_df["AdsDate"], errors="coerce")
                    ads_df["AdsSpend"] = pd.to_numeric(ads_df["AdsSpend"], errors="coerce").fillna(0)
            elif ads_source == "Montant total (période filtrée)":
                ads_total_manual = st.number_input("💸 Total Ads pour la période filtrée", min_value=0.0, value=0.0, step=10.0)

        # ---------- Conversions de base ----------
        df["VentesBrutes"] = safe_num(df[col_vente]).fillna(0)

        if col_qte == "(Aucune)":
            df["Quantité"] = 1
        else:
            df["Quantité"] = safe_num(df[col_qte]).fillna(0)

        # Frais logistiques
        if col_shipping == "(Aucune)":
            df["FraisLivraison"] = shipping_fixe if shipping_fixe is not None else 0.0
        else:
            df["FraisLivraison"] = safe_num(df[col_shipping]).fillna(0)

        if col_autres == "(Aucune)":
            df["AutresFrais"] = autres_fixe if autres_fixe is not None else 0.0
        else:
            df["AutresFrais"] = safe_num(df[col_autres]).fillna(0)

        df["Date"] = pd.to_datetime(df[col_date], errors="coerce")

        # COGS / PrixArticle
        if source_prix == "Colonne existante":
            df["PrixArticle"] = safe_num(df[col_prix_article_opt]).fillna(0.0)
        elif source_prix == "Prix fixe":
            df["PrixArticle"] = prix_article_fixe
        else:
            merge_df = st.session_state.cost_editor_df.rename(columns={"Produit":"__PROD__", "PrixArticle":"PrixArticle"})
            df = df.merge(merge_df, left_on=col_product, right_on="__PROD__", how="left")
            df.drop(columns=["__PROD__"], inplace=True)
            df["PrixArticle"] = safe_num(df["PrixArticle"]).fillna(0.0)

        # Ventes nettes avant Ads (si تختار خصم المصاريف من المداخيل)
        if incl_fees:
            df["Ventes"] = df["VentesBrutes"] - (df["FraisLivraison"] + df["AutresFrais"])
        else:
            df["Ventes"] = df["VentesBrutes"]

        # ---------- Filtres temporels/statut ----------
        min_date, max_date = df["Date"].min(), df["Date"].max()
        date_range = st.date_input("📅 Filtrer par date", [min_date, max_date])
        filtered = df[(df["Date"].dt.date >= date_range[0]) & (df["Date"].dt.date <= date_range[1])].copy()

        if col_status != "(Aucune)":
            vals = sorted(filtered[col_status].dropna().unique().tolist())
            chosen = st.multiselect("🏷️ Filtrer par statut", vals)
            if chosen:
                filtered = filtered[filtered[col_status].isin(chosen)]

        # ---------- Allocation Ads ----------
        filtered["AdsAllocated"] = 0.0
        ads_breakdown = None

        if 'col_ads_in_sales' in locals() and col_ads_in_sales:
            filtered["AdsAllocated"] = safe_num(filtered[col_ads_in_sales]).fillna(0.0)

        if 'ads_df' in locals() and ads_df is not None and len(ads_df):
            ads_period = ads_df[(ads_df["AdsDate"].dt.date >= date_range[0]) & (ads_df["AdsDate"].dt.date <= date_range[1])].copy()
            if len(ads_period):
                grp_cols = ["AdsDate"]
                if "AdsChannel" in ads_period.columns:
                    grp_cols.append("AdsChannel")
                daily_ads = ads_period.groupby(grp_cols, dropna=False)["AdsSpend"].sum().reset_index()

                filtered["OrderCount"] = 1
                base_key = "VentesBrutes" if st.session_state.get("ads_alloc_mode","par ventes (montant)") == "par ventes (montant)" else "OrderCount"

                alloc_list = []
                for _, row in daily_ads.iterrows():
                    d = row["AdsDate"].date()
                    ch = row["AdsChannel"] if "AdsChannel" in daily_ads.columns else None
                    mask = (filtered["Date"].dt.date == d)
                    base_sum = filtered.loc[mask, base_key].sum()
                    if base_sum > 0:
                        alloc = (filtered.loc[mask, base_key] / base_sum) * float(row["AdsSpend"])
                        tmp = filtered.loc[mask, ["Date"]].copy()
                        tmp["Alloc"] = alloc.values
                        tmp["Channel"] = ch if ch is not None else "All"
                        alloc_list.append(tmp)
                if alloc_list:
                    alloc_df = pd.concat(alloc_list, ignore_index=True)
                    filtered = filtered.reset_index().merge(alloc_df.groupby(["Date"]).agg(AdsAllocated=("Alloc","sum")).reset_index(),
                                                            on="Date", how="left").set_index("index")
                    filtered["AdsAllocated"] = filtered["AdsAllocated"].fillna(0.0)
                    ads_breakdown = alloc_df.groupby("Channel")["Alloc"].sum().reset_index().rename(columns={"Alloc":"AdsSpend"})

        if 'ads_total_manual' in locals() and ads_total_manual and ads_total_manual > 0:
            filtered["OrderCount"] = 1
            base_key = "VentesBrutes" if st.session_state.get("ads_alloc_mode","par ventes (montant)") == "par ventes (montant)" else "OrderCount"
            base_sum = filtered[base_key].sum()
            if base_sum > 0:
                filtered["AdsAllocated"] = (filtered[base_key] / base_sum) * ads_total_manual

        # ---------- Calculs finaux ----------
        filtered["CoutTotal"] = filtered["PrixArticle"] * filtered["Quantité"]
        filtered["ProfitAvantAds"] = filtered["Ventes"] - filtered["CoutTotal"]
        filtered["ProfitApresAds"] = filtered["ProfitAvantAds"] - filtered["AdsAllocated"]
        filtered["Marge %"] = np.where(filtered["Ventes"]>0, (filtered["ProfitAvantAds"]/filtered["Ventes"])*100, 0)
        filtered["Marge % Après Ads"] = np.where(filtered["Ventes"]>0, (filtered["ProfitApresAds"]/filtered["Ventes"])*100, 0)

        # ---------- KPIs (brand cards) ----------
        c1,c2,c3,c4,c5 = st.columns(5)
        with c1: kpi("💰 Total Ventes", f"{filtered['Ventes'].sum():,.2f}")
        with c2: kpi("💵 Profit (avant Ads)", f"{filtered['ProfitAvantAds'].sum():,.2f}")
        with c3: kpi("📣 Ads Spend (alloc.)", f"{filtered['AdsAllocated'].sum():,.2f}")
        roas = (filtered["Ventes"].sum() / filtered["AdsAllocated"].sum()) if filtered["AdsAllocated"].sum() > 0 else None
        cpo = (filtered["AdsAllocated"].sum() / len(filtered)) if len(filtered) > 0 else None
        with c4: kpi("📈 ROAS", f"{roas:,.2f}" if roas else "—", "Ventes / Ads")
        with c5: kpi("🎯 CPO", f"{cpo:,.2f}" if cpo else "—", "Coût par commande")

        st.markdown("---")

        # ---------- Charts PRO (brand colors) ----------
        st.subheader("📈 Évolution journalière — Ventes vs Profit (après Ads)")
        by_day = filtered.groupby(filtered["Date"].dt.date).agg(
            Ventes=("Ventes","sum"),
            ProfitAvantAds=("ProfitAvantAds","sum"),
            Ads=("AdsAllocated","sum"),
            ProfitApresAds=("ProfitApresAds","sum"),
            COGS=("CoutTotal","sum"),
            Ship=("FraisLivraison","sum"),
            Divers=("AutresFrais","sum")
        ).reset_index().rename(columns={"Date":"Jour"})

        line_fig = go.Figure()
        line_fig.add_trace(go.Scatter(x=by_day["Date"], y=by_day["Ventes"], mode="lines+markers", name="Ventes", line=dict(width=3, color=BRAND_GOLD)))
        line_fig.add_trace(go.Scatter(x=by_day["Date"], y=by_day["ProfitApresAds"], mode="lines+markers", name="Profit après Ads", line=dict(width=3)))
        line_fig.update_layout(hovermode="x unified", legend=dict(orientation="h"), margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(line_fig, use_container_width=True)

        st.subheader("🧱 Décomposition quotidienne — Coûts empilés vs Ventes")
        stacked = by_day.melt(id_vars=["Date"], value_vars=["COGS","Ship","Divers","Ads"],
                              var_name="Type", value_name="Montant")
        cost_fig = px.bar(stacked, x="Date", y="Montant", color="Type", title="Coûts (COGS, Livraison, Divers, Ads)")
        cost_fig.add_trace(go.Scatter(x=by_day["Date"], y=by_day["Ventes"], mode="lines", name="Ventes", line=dict(width=2, color=BRAND_GOLD)))
        cost_fig.update_layout(hovermode="x unified", legend=dict(orientation="h"), margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(cost_fig, use_container_width=True)

        st.subheader("📊 ROAS par Jour")
        by_day["ROAS"] = np.where(by_day["Ads"]>0, by_day["Ventes"]/by_day["Ads"], np.nan)
        roas_fig = px.line(by_day, x="Date", y="ROAS", title="ROAS (Ventes / Ads)")
        st.plotly_chart(roas_fig, use_container_width=True)

        if col_status != "(Aucune)":
            st.subheader("🏷️ Répartition des Ventes par Statut")
            pie_df = filtered.groupby(col_status, dropna=False)["Ventes"].sum().reset_index()
            st.plotly_chart(px.pie(pie_df, names=col_status, values="Ventes", title="Ventes par Statut"), use_container_width=True)

        # ---------- Détails & Export ----------
        st.subheader("📋 Données calculées (aperçu)")
        show_cols = ["Date"]
        if col_status != "(Aucune)": show_cols.append(col_status)
        if col_product != "(Aucune)": show_cols.append(col_product)
        if col_city    != "(Aucune)": show_cols.append(col_city)
        show_cols += ["VentesBrutes","FraisLivraison","AutresFrais","Ventes","Quantité","PrixArticle","CoutTotal",
                      "AdsAllocated","ProfitAvantAds","ProfitApresAds","Marge %","Marge % Après Ads"]
        show_cols = [c for c in show_cols if c in filtered.columns]
        st.dataframe(filtered[show_cols].head(500), use_container_width=True)

        st.subheader("📥 Export")
        st.download_button("⬇️ Télécharger CSV (filtré)",
                           filtered.to_csv(index=False).encode("utf-8-sig"),
                           "ventes_filtrees_avec_ads.csv", "text/csv")

        st.markdown("<small style='color:#9CA3AF'>Thème Corella: noir + or • Charts Plotly Dark • © Corella Store</small>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erreur: {e}")
else:
    st.info("📌 Veuillez importer un fichier Excel pour commencer.")

