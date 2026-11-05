"""CRM Pro — point d'entrée Streamlit : démarrage, connexion, menu latéral et routage des pages."""

import hashlib
import sys
from pathlib import Path

import streamlit as st

# --- Mise à jour du code sans redémarrage (Streamlit Cloud) ------------------------------------------
# Quand GitHub pousse une nouvelle version, le serveur relance ce script mais garde en mémoire les
# anciens modules (db.*, modules.*, config). Si la version a changé, on les oublie pour charger les
# nouveaux, et on vide le cache (connexion à la base, migration).
_RACINE = Path(__file__).parent
_PROJET = {"config", "db", "modules", "demo_data"}
_fichiers = [
    *sorted(_RACINE.glob("*.py")),
    *sorted((_RACINE / "db").glob("*.py")),
    *sorted((_RACINE / "modules").glob("*.py")),
]
_version = hashlib.md5(
    "|".join(f"{p.name}:{p.stat().st_mtime_ns}:{p.stat().st_size}" for p in _fichiers).encode()
).hexdigest()
_precedente = getattr(sys, "_crm_version", None)
_perimes = _precedente != _version if _precedente else any(n in sys.modules for n in _PROJET)
if _perimes:
    for _nom in [n for n in sys.modules if n.split(".")[0] in _PROJET]:
        del sys.modules[_nom]
    st.cache_resource.clear()
    st.cache_data.clear()
sys._crm_version = _version

import config
from db import alertes as A
from db.models import init_db
from db.utils import get_params
from modules import (
    aide,
    alertes,
    auth,
    base_donnees,
    catalogue,
    clients,
    dashboard,
    dettes,
    entrees,
    parametres,
    produits,
    ui,
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
config.POLICE = params.get("police", "Inter")
st.markdown(config.css_police(config.POLICE), unsafe_allow_html=True)

# Pages : (clé, icône, libellé, fonction)
MENU = [
    (
        None,
        [
            ("Accueil", ":material/space_dashboard:", "Tableau de bord", dashboard.show_dashboard),
            ("Alertes", ":material/notifications:", "Alertes", alertes.show_alertes),
        ],
    ),
    (
        "Vendre",
        [
            ("Ventes", ":material/point_of_sale:", "Nouvelle vente", ventes.show_ventes),
            ("Dettes", ":material/account_balance_wallet:", "Dettes clients", dettes.show_dettes),
        ],
    ),
    (
        "Stock",
        [
            ("Entrees", ":material/move_to_inbox:", "Entrée de stock", entrees.show_entrees),
            ("Produits", ":material/inventory_2:", "État du stock", produits.show_produits),
            ("Catalogue", ":material/category:", "Base produits", catalogue.show_catalogue),
        ],
    ),
    (
        "Gérer",
        [
            ("Clients", ":material/group:", "Clients", clients.show_clients),
            ("Documents", ":material/receipt_long:", "Ventes & documents", ventes_documents.show_ventes_documents),
        ],
    ),
    (
        "Réglages",
        [
            ("Paramètres", ":material/settings:", "Paramètres", parametres.show_parametres),
            ("Base", ":material/database:", "Base de données", base_donnees.show_base),
            ("Aide", ":material/help:", "Guide rapide", aide.show_aide),
        ],
    ),
]
PAGES = {cle: fn for _, items in MENU for cle, _, _, fn in items}

page = st.session_state.get("page", "Accueil")
if page not in PAGES:
    page = "Accueil"
st.session_state["page"] = page

compte = A.compter(A.alertes_memorisees(params))
st.session_state["_barre"] = {  # pour la barre du haut de chaque page (config.entete)
    "lieu": params.get("boutique_adresse", ""),
    "alertes": compte[A.CRITIQUE] + compte[A.ATTENTION],
    "boutique": params["boutique_nom"],
}

with st.sidebar:
    st.markdown(ui.logo_menu(params["boutique_nom"]), unsafe_allow_html=True)
    for section, items in MENU:
        if section:
            st.markdown(f"<p class='crm-menu-title'>{section}</p>", unsafe_allow_html=True)
        for cle, icone, libelle, _ in items:
            texte = libelle
            if cle == "Alertes" and compte[A.CRITIQUE] + compte[A.ATTENTION]:
                texte += f" ({compte[A.CRITIQUE] + compte[A.ATTENTION]})"
            if cle == "Dettes" and compte["dette_retard"]:
                texte += f" ({compte['dette_retard']} en retard)"
            st.button(  # on_click : la page change avant la relance, sans 2e chargement
                texte,
                key=f"menu_{cle}",
                icon=icone,
                width="stretch",
                type="primary" if cle == page else "secondary",
                on_click=config.aller_vers,
                args=(cle,),
            )
    st.markdown(ui.pied_menu(), unsafe_allow_html=True)
    auth.bouton_deconnexion()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon=":material/check_circle:")

PAGES[page]()
