"""CRM Pro — point d'entrée Streamlit : démarrage, connexion, menu latéral et routage des pages."""

from pathlib import Path

import streamlit as st

import config
from db import alertes as A
from db.models import get_session, init_db
from db.utils import get_params
from modules import (
    aide,
    alertes,
    auth,
    base_donnees,
    clients,
    dashboard,
    dettes,
    parametres,
    produits,
    ventes,
    ventes_documents,
)

config.setup_page()


@st.cache_resource
def demarrage():
    """Une seule fois par serveur : création / migration de la base, données de démo si DEMO_MODE."""
    init_db()
    if str(auth.secret("DEMO_MODE", "false")).lower() in ("1", "true", "oui", "yes"):
        import demo_data

        demo_data.main()
    return True


demarrage()
st.markdown(
    f"<style>{(Path(__file__).parent / 'static' / 'styles.css').read_text('utf-8')}</style>", unsafe_allow_html=True
)

if not auth.verifier_acces():
    st.stop()

params = get_params()
config.DEVISE = params["devise"]

# Pages : (clé, icône, libellé, fonction)
MENU = [
    (
        None,
        [
            ("Accueil", "🏠", "Tableau de bord", dashboard.show_dashboard),
            ("Alertes", "🔔", "Alertes", alertes.show_alertes),
        ],
    ),
    (
        "Vendre",
        [
            ("Ventes", "🛒", "Nouvelle vente", ventes.show_ventes),
            ("Dettes", "💳", "Dettes clients", dettes.show_dettes),
        ],
    ),
    (
        "Gérer",
        [
            ("Clients", "👥", "Clients", clients.show_clients),
            ("Produits", "📦", "Produits & stock", produits.show_produits),
            ("Documents", "📄", "Ventes & documents", ventes_documents.show_ventes_documents),
        ],
    ),
    (
        "Réglages",
        [
            ("Paramètres", "⚙️", "Paramètres", parametres.show_parametres),
            ("Base", "🗄️", "Base de données", base_donnees.show_base),
            ("Aide", "❓", "Guide rapide", aide.show_aide),
        ],
    ),
]
PAGES = {cle: fn for _, items in MENU for cle, _, _, fn in items}

page = st.session_state.get("page", "Accueil")
if page not in PAGES:
    page = "Accueil"
st.session_state["page"] = page

with get_session() as s:
    compte = A.compter(A.calculer_alertes(s, params))

with st.sidebar:
    st.markdown(
        f"<p class='crm-logo'>💼 CRM Pro</p><p class='crm-shop'>{params['boutique_nom']}</p>", unsafe_allow_html=True
    )
    for section, items in MENU:
        if section:
            st.markdown(f"<p class='crm-menu-title'>{section}</p>", unsafe_allow_html=True)
        for cle, icone, libelle, _ in items:
            texte = f"{icone}  {libelle}"
            if cle == "Alertes" and compte[A.CRITIQUE] + compte[A.ATTENTION]:
                texte += f"  · {compte[A.CRITIQUE] + compte[A.ATTENTION]}"
            if cle == "Dettes" and compte["dette_retard"]:
                texte += f"  · 🔴 {compte['dette_retard']}"
            if st.button(
                texte, key=f"menu_{cle}", use_container_width=True, type="primary" if cle == page else "secondary"
            ):
                st.session_state["page"] = cle
                st.rerun()
    st.divider()
    auth.bouton_deconnexion()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

PAGES[page]()
