"""Produits & stock : modification directe dans le tableau, ajout, réapprovisionnement."""

import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db.models import Produit, get_session
from db.utils import get_param


def _categories(session):
    existantes = {p.categorie for p in session.query(Produit) if p.categorie}
    return sorted(existantes | set(config.CATEGORIES_DEFAUT))


def show_produits():
    seuil = int(get_param("seuil_stock"))
    with get_session() as session:
        config.entete(
            "Produits & stock", "Modifiez prix, stock et seuils directement dans le tableau, puis enregistrez."
        )
        produits = session.query(Produit).order_by(Produit.categorie, Produit.nom).all()
        ruptures = [p for p in produits if (p.stock or 0) <= 0]
        faibles = [p for p in produits if 0 < (p.stock or 0) <= p.seuil(seuil)]
        config.kpis(
            [
                (
                    "Produits",
                    len(produits),
                    config.SECONDARY_BLUE,
                    f"{len({p.categorie for p in produits})} catégories",
                ),
                (
                    "Valeur du stock",
                    fmt_money(sum((p.prix_achat or p.prix or 0) * max(p.stock or 0, 0) for p in produits)),
                    config.SUCCESS_GREEN,
                    "au prix d'achat",
                ),
                (
                    "Ruptures",
                    len(ruptures),
                    config.DANGER_RED if ruptures else config.MUTED,
                    ", ".join(p.nom for p in ruptures[:3]),
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
        a, b, c = st.columns([1.2, 1.6, 3], vertical_alignment="bottom")
        if a.button("➕ Nouveau produit", type="primary", use_container_width=True):
            _dialog_produit(_categories(session))
        if b.button("📥 Réception de marchandise", use_container_width=True):
            _dialog_reception([(p.id, p.nom, p.unite) for p in produits])
        filtre = c.text_input("Filtrer", placeholder="🔎  Filtrer les produits…", label_visibility="collapsed")
        if not produits:
            st.info("Aucun produit pour l'instant.")
            return
        if filtre:
            produits = [p for p in produits if filtre.lower() in f"{p.nom} {p.categorie} {p.reference}".lower()]

        def statut(p):
            if (p.stock or 0) <= 0:
                return "🔴 Rupture"
            return "🟠 Faible" if p.stock <= p.seuil(seuil) else "🟢 OK"

        df = pd.DataFrame(
            [
                {
                    "id": p.id,
                    "Produit": p.nom,
                    "Catégorie": p.categorie or "Divers",
                    "Unité": p.unite or "pièce",
                    "Prix de vente": int(p.prix or 0),
                    "Prix d'achat": int(p.prix_achat or 0),
                    "Stock": int(p.stock or 0),
                    "Seuil d'alerte": p.seuil_alerte,
                    "État": statut(p),
                }
                for p in produits
            ]
        )
        df["Seuil d'alerte"] = df["Seuil d'alerte"].astype("Int64")
        st.caption(f"Seuil d'alerte vide = seuil général ({seuil}). Double-cliquez sur une case pour la modifier.")
        edite = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            key="editeur_produits",
            disabled=["État"],
            column_config={
                "id": None,
                "Produit": st.column_config.TextColumn(required=True, width="medium"),
                "Catégorie": st.column_config.SelectboxColumn(options=_categories(session), required=True),
                "Unité": st.column_config.SelectboxColumn(options=config.UNITES, required=True, width="small"),
                "Prix de vente": st.column_config.NumberColumn(min_value=0, step=50, format="localized"),
                "Prix d'achat": st.column_config.NumberColumn(
                    min_value=0, step=50, format="localized", help="Sert à calculer votre bénéfice"
                ),
                "Stock": st.column_config.NumberColumn(min_value=0, step=1, width="small"),
                "Seuil d'alerte": st.column_config.NumberColumn(
                    min_value=0, step=1, width="small", help="Alerte quand le stock descend à ce niveau"
                ),
            },
        )
        if not _norm(edite).equals(_norm(df)):
            st.warning("Des modifications ne sont pas encore enregistrées.")
            if st.button("💾 Enregistrer les modifications", type="primary"):
                noms = [str(n).strip() for n in edite["Produit"]]
                if len(set(noms)) != len(noms) or not all(noms):
                    st.error("Deux produits ne peuvent pas avoir le même nom, et le nom est obligatoire.")
                    return
                for _, r in edite.iterrows():
                    p = session.get(Produit, int(r["id"]))
                    p.nom, p.categorie, p.unite = str(r["Produit"]).strip(), r["Catégorie"], r["Unité"]
                    p.prix, p.prix_achat, p.stock = r["Prix de vente"], r["Prix d'achat"], int(r["Stock"])
                    p.seuil_alerte = None if pd.isna(r["Seuil d'alerte"]) else int(r["Seuil d'alerte"])
                session.commit()
                st.session_state.pop("editeur_produits", None)
                config.flash("Produits mis à jour.")
                st.rerun()


def _norm(d):
    return d.fillna(-1).astype(str).reset_index(drop=True)


@st.dialog("➕ Nouveau produit")
def _dialog_produit(categories):
    with st.form("nouveau_produit"):
        nom = st.text_input("Nom du produit *", placeholder="Ex : Ciment CPJ 45 - 50 kg")
        a, b = st.columns(2)
        categorie = a.selectbox(
            "Catégorie",
            categories,
            index=categories.index("Divers"),
            accept_new_options=True,
            help="Choisissez ou tapez une nouvelle catégorie",
        )
        unite = b.selectbox("Unité de vente", config.UNITES)
        a, b = st.columns(2)
        prix = a.number_input("Prix de vente (FCFA)", min_value=0, step=50)
        achat = b.number_input("Prix d'achat (FCFA)", min_value=0, step=50, help="Pour calculer le bénéfice")
        a, b = st.columns(2)
        stock = a.number_input("Quantité en stock", min_value=0, step=1)
        seuil = b.number_input("Alerter quand il reste…", min_value=0, step=1, value=int(get_param("seuil_stock")))
        if st.form_submit_button("Ajouter", type="primary", use_container_width=True):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
                return
            with get_session() as session:
                if session.query(Produit).filter_by(nom=nom.strip()).first():
                    st.error("Ce produit existe déjà.")
                    return
                session.add(
                    Produit(
                        nom=nom.strip(),
                        categorie=categorie or "Divers",
                        unite=unite,
                        prix=prix,
                        prix_achat=achat,
                        stock=stock,
                        seuil_alerte=seuil,
                    )
                )
                session.commit()
            config.flash(f"Produit {nom} ajouté.")
            st.rerun()


@st.dialog("📥 Réception de marchandise")
def _dialog_reception(produits):
    st.caption("Ajoutez au stock ce que vous venez de recevoir du fournisseur.")
    noms = {pid: f"{nom} ({unite or 'pièce'})" for pid, nom, unite in produits}
    with st.form("reception"):
        pid = st.selectbox(
            "Produit", list(noms), format_func=noms.get, index=None, placeholder="Tapez les premières lettres…"
        )
        qte = st.number_input("Quantité reçue", min_value=1, step=1)
        achat = st.number_input("Nouveau prix d'achat (laisser 0 pour ne pas changer)", min_value=0, step=50)
        if st.form_submit_button("Ajouter au stock", type="primary", use_container_width=True):
            if pid is None:
                st.error("Choisissez un produit.")
                return
            with get_session() as session:
                p = session.get(Produit, pid)
                p.stock = (p.stock or 0) + qte
                if achat:
                    p.prix_achat = achat
                session.commit()
                config.flash(f"+{qte} {p.unite or 'pièce'}(s) de {p.nom} · stock : {p.stock}")
            st.session_state.pop("editeur_produits", None)
            st.rerun()
