"""Page 🔔 Alertes : tout ce qui demande une action, du plus urgent au moins urgent."""

from html import escape

import streamlit as st

import config
from config import fmt_money
from db import alertes as A
from db import dettes as D
from db.models import get_session
from db.utils import get_params

COULEUR = {A.CRITIQUE: config.DANGER_RED, A.ATTENTION: config.WARNING_ORANGE, A.INFO: config.MUTED}
FAMILLES = {
    "Tout": None,
    "💳 Dettes": {"dette_retard", "echeance_aujourdhui", "echeance_proche", "plafond"},
    "📦 Stock": {"rupture", "stock_faible", "perte", "dormant", "sans_prix_achat"},
}


def ligne_alerte(a, params, cle):
    """Une alerte = une ligne : qui/quoi, détail, montant, boutons d'action."""
    c = COULEUR[a.niveau]
    gauche, milieu, droite = st.columns([5, 2, 3], vertical_alignment="center")
    gauche.markdown(
        f"<div class='crm-alert' style='--c:{c};margin:0'>{a.icone} <b>{escape(a.titre)}</b> · {escape(a.detail)}</div>",
        unsafe_allow_html=True,
    )
    if a.montant:
        milieu.markdown(f"**{fmt_money(a.montant)}**")
    b1, b2 = droite.columns(2)
    if a.page and b1.button(a.action, key=f"act_{cle}", use_container_width=True):
        if a.produit_id:
            st.session_state["produit_cible"] = a.produit_id
        config.aller_a(a.page, **a.etat)
    if a.dette is not None:
        s = D.situation_dette(a.dette)
        msg = D.message_relance(
            params["message_relance"],
            a.client,
            a.dette.reste,
            s["prochaine_date"],
            params["boutique_nom"],
            params["boutique_telephone"],
            fmt_money,
        )
        lien = D.lien_whatsapp(a.client.telephone, msg)
        if lien:
            b2.link_button("📲 WhatsApp", lien, use_container_width=True)


def show_alertes():
    params = get_params()
    with get_session() as session:
        alertes = A.calculer_alertes(session, params)
        n = A.compter(alertes)
        config.entete("Alertes", "Tout ce qui demande votre attention, du plus urgent au moins urgent.")
        config.kpis(
            [
                ("🔴 Urgent", n[A.CRITIQUE], config.DANGER_RED, "retards de paiement, ruptures"),
                ("🟠 À surveiller", n[A.ATTENTION], config.WARNING_ORANGE, "paiements proches, stock faible…"),
                ("ℹ️ Pour information", n[A.INFO], config.MUTED, "stock dormant, prix manquants"),
            ]
        )
        st.write("")
        famille = st.segmented_control("Afficher", list(FAMILLES), default="Tout", label_visibility="collapsed")
        types = FAMILLES.get(famille or "Tout")
        visibles = [a for a in alertes if types is None or a.type in types]
        if not visibles:
            st.success("✅ Aucune alerte. Tout est en ordre.")
            return

        for t, (icone, libelle) in A.TYPES.items():
            groupe = [a for a in visibles if a.type == t]
            if not groupe:
                continue
            total = sum(a.montant for a in groupe)
            entete = f"{icone} {libelle} ({len(groupe)})" + (f" · {fmt_money(total)}" if total else "")
            info = groupe[0].niveau == A.INFO
            with st.expander(entete, expanded=not info):
                for i, a in enumerate(groupe):
                    ligne_alerte(a, params, f"{t}_{i}")
