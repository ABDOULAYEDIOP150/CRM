"""Produits & stock : modification directe dans le tableau, ajout, réapprovisionnement."""

import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db.models import Produit, get_session
from db.utils import get_param


def show_produits():
    seuil = int(get_param("seuil_stock"))
    with get_session() as session:
        config.entete("Produits & stock", "Modifiez prix et stock directement dans le tableau, puis enregistrez.")
        produits = session.query(Produit).order_by(Produit.nom).all()
        faibles = [p for p in produits if p.stock <= seuil]
        config.kpis(
            [
                ("Produits", len(produits), config.SECONDARY_BLUE, ""),
                (
                    "Valeur du stock",
                    fmt_money(sum(p.prix * p.stock for p in produits)),
                    config.SUCCESS_GREEN,
                    "au prix de vente",
                ),
                (
                    "Stock faible",
                    len(faibles),
                    config.WARNING_ORANGE if faibles else config.MUTED,
                    ", ".join(p.nom for p in faibles[:3]),
                ),
            ]
        )
        st.write("")
        if st.button("➕ Nouveau produit", type="primary"):
            _dialog_produit()
        if not produits:
            st.info("Aucun produit pour l'instant.")
            return

        df = pd.DataFrame(
            [
                {
                    "id": p.id,
                    "Produit": p.nom,
                    "Prix de vente": int(p.prix or 0),
                    "Prix d'achat": int(p.prix_achat or 0),
                    "Stock": int(p.stock or 0),
                    "Alerte": "⚠️ Faible" if p.stock <= seuil else "",
                }
                for p in produits
            ]
        )
        edite = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            key="editeur_produits",
            disabled=["Alerte"],
            column_config={
                "id": None,
                "Produit": st.column_config.TextColumn(required=True),
                "Prix de vente": st.column_config.NumberColumn(min_value=0, step=50, format="localized"),
                "Prix d'achat": st.column_config.NumberColumn(
                    min_value=0, step=50, format="localized", help="Sert à calculer votre marge"
                ),
                "Stock": st.column_config.NumberColumn(min_value=0, step=1),
            },
        )
        modifs = edite.compare(df) if not edite.equals(df) else None
        if modifs is not None and not modifs.empty:
            st.warning(f"{len(modifs)} ligne(s) modifiée(s), pensez à enregistrer.")
            if st.button("💾 Enregistrer les modifications", type="primary"):
                noms = [n.strip() for n in edite["Produit"]]
                if len(set(noms)) != len(noms) or not all(noms):
                    st.error("Deux produits ne peuvent pas avoir le même nom, et le nom est obligatoire.")
                    return
                for _, r in edite.iterrows():
                    p = session.get(Produit, int(r["id"]))
                    p.nom, p.prix, p.prix_achat, p.stock = (
                        r["Produit"].strip(),
                        r["Prix de vente"],
                        r["Prix d'achat"],
                        r["Stock"],
                    )
                session.commit()
                st.session_state.pop("editeur_produits", None)
                config.flash("Produits mis à jour.")
                st.rerun()


@st.dialog("➕ Nouveau produit")
def _dialog_produit():
    with st.form("nouveau_produit"):
        nom = st.text_input("Nom du produit *", placeholder="Ex : Riz parfumé 25 kg")
        a, b = st.columns(2)
        prix = a.number_input("Prix de vente (FCFA)", min_value=0, step=100)
        achat = b.number_input("Prix d'achat (FCFA)", min_value=0, step=100, help="Facultatif, pour la marge")
        stock = st.number_input("Quantité en stock", min_value=0, step=1)
        if st.form_submit_button("Ajouter", type="primary", use_container_width=True):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
                return
            with get_session() as session:
                if session.query(Produit).filter_by(nom=nom.strip()).first():
                    st.error("Ce produit existe déjà.")
                    return
                session.add(Produit(nom=nom.strip(), prix=prix, prix_achat=achat, stock=stock))
                session.commit()
            config.flash(f"Produit {nom} ajouté.")
            st.rerun()
