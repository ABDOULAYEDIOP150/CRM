"""Paramètres : coordonnées de la boutique, réglages des alertes, message de relance, sauvegarde."""

import streamlit as st

import config
from db.models import init_db
from db.utils import get_params, set_params
from modules.base_donnees import _export_excel


def show_parametres():
    config.entete("Paramètres", "Boutique, alertes et sauvegarde")
    p = get_params()
    with st.form("parametres"):
        boutique, alertes = st.columns([1.4, 1], gap="large")
        with boutique:
            st.markdown("#### Boutique")
            st.caption("Affiché sur les factures, reçus et relances.")
            nom = st.text_input("Nom de la boutique", p["boutique_nom"])
            a, b = st.columns(2)
            adresse = a.text_input("Adresse", p["boutique_adresse"])
            tel = b.text_input("Téléphone (Wave / Orange Money)", p["boutique_telephone"])
            email = a.text_input("Email", p["boutique_email"])
            ninea = b.text_input("NINEA", p["boutique_ninea"])
            rccm = a.text_input("RCCM", p["boutique_rccm"])
        with alertes:
            st.markdown("#### Alertes")
            st.caption("Quand l'application vous prévient.")
            seuil = st.number_input("Stock faible à partir de", min_value=0, value=int(p["seuil_stock"]))
            jours = st.number_input(
                "Rappel avant un paiement (jours)", min_value=0, max_value=30, value=int(p["jours_alerte_echeance"])
            )
            dormant = st.number_input(
                "Produit qui ne se vend pas après (jours)", min_value=7, max_value=365,
                value=int(p["jours_stock_dormant"]),
            )  # fmt: skip
        with st.expander("Message de relance WhatsApp"):
            msg = st.text_area(
                "Message",
                p["message_relance"],
                height=100,
                label_visibility="collapsed",
                help="Remplacés automatiquement : {client} {reste} {echeance} {boutique} {telephone}",
            )
        if st.form_submit_button("Enregistrer", type="primary", width="stretch", icon=":material/save:"):
            set_params(
                {
                    "boutique_nom": nom,
                    "boutique_adresse": adresse,
                    "boutique_telephone": tel,
                    "boutique_email": email,
                    "boutique_ninea": ninea,
                    "boutique_rccm": rccm,
                    "seuil_stock": seuil,
                    "jours_alerte_echeance": jours,
                    "jours_stock_dormant": dormant,
                    "message_relance": msg,
                }
            )
            config.flash("Paramètres enregistrés.")
            st.rerun()

    st.write("")
    with config.carte():
        g, d = st.columns([3, 1.3], vertical_alignment="center")
        g.markdown("#### Sauvegarde")
        g.caption("Toutes vos données (produits, ventes, clients, dettes) dans un fichier Excel.")
        if "export_xlsx" not in st.session_state:
            if d.button("Préparer la sauvegarde", width="stretch", icon=":material/backup:"):
                st.session_state["export_xlsx"] = _export_excel(init_db())
                st.rerun()
        else:
            d.download_button(
                "Télécharger",
                st.session_state.pop("export_xlsx"),
                "sauvegarde_boutique.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                type="primary",
                icon=":material/download:",
            )
