import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db.models import Produit, get_session
from db.utils import get_param


def show_produits():
    st.markdown("<h2 style='color: #1e3a8a;'>📦 Gestion des produits</h2>", unsafe_allow_html=True)
    seuil = int(get_param("seuil_stock"))
    with get_session() as session:
        col1, col2 = st.columns([2, 3])
        with col1:
            produits = session.query(Produit).order_by(Produit.nom).all()
            p = config.choisir("Produit", produits, lambda x: f"✏️ {x.nom}", nouveau="➕ Nouveau produit")
            with st.form("form_produit", clear_on_submit=p is None):
                nom = st.text_input("Nom du produit *", value=p.nom if p else "")
                prix = st.number_input(
                    "Prix de vente (FCFA)", min_value=0, step=100, value=int(p.prix or 0) if p else 0
                )
                prix_achat = st.number_input(
                    "Prix d'achat (FCFA, pour la marge)",
                    min_value=0,
                    step=100,
                    value=int(p.prix_achat or 0) if p else 0,
                )
                if p:
                    ajout = st.number_input(f"Réapprovisionner (stock actuel : {p.stock})", min_value=0, step=1)
                else:
                    ajout = st.number_input("Stock initial", min_value=0, step=1)
                if st.form_submit_button("Enregistrer", use_container_width=True):
                    if not nom:
                        st.error("Le nom est obligatoire.")
                    elif session.query(Produit).filter(Produit.nom == nom, Produit.id != (p.id if p else -1)).first():
                        st.error("❌ Un produit porte déjà ce nom")
                    else:
                        if p is None:
                            p = Produit(stock=0)
                            session.add(p)
                        p.nom, p.prix, p.prix_achat = nom, prix, prix_achat
                        p.stock = (p.stock or 0) + ajout
                        session.commit()
                        st.session_state["flash"] = f"✅ Produit {nom} enregistré."
                        st.rerun()

        with col2:
            st.markdown("### 📋 Inventaire")
            produits = session.query(Produit).order_by(Produit.nom).all()
            if not produits:
                st.info("Aucun produit")
                return
            df = pd.DataFrame(
                [
                    {
                        "Produit": x.nom,
                        "Prix": x.prix,
                        "Prix d'achat": x.prix_achat or 0,
                        "Marge unit.": (x.prix - x.prix_achat) if x.prix_achat else None,
                        "Stock": x.stock,
                        "Valeur stock": x.prix * x.stock,
                        "Statut": "⚠️ Stock faible" if x.stock <= seuil else "✅ OK",
                    }
                    for x in produits
                ]
            )
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    c: st.column_config.NumberColumn(format="%d")
                    for c in ["Prix", "Prix d'achat", "Marge unit.", "Valeur stock"]
                },
            )
            st.caption(f"Valeur totale du stock : {fmt_money(df['Valeur stock'].sum())}")
            alertes = [x.nom for x in produits if x.stock <= seuil]
            if alertes:
                st.warning("⚠️ Stock faible : " + ", ".join(alertes))
