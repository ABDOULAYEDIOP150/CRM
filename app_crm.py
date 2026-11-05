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
    alertes,
    auth,
    catalogue,
    clients,
    dashboard,
    dettes,
    entrees,
    parametres,
    ui,
    ventes,
    ventes_documents,
)

config.setup_page()
st.session_state["_n_carte"] = 0  # numérotation des cartes de cette page (config.carte)


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
            ("Ventes", ":material/point_of_sale:", "Nouvelle vente", ventes.show_ventes),
            ("Dettes", ":material/account_balance_wallet:", "Dettes clients", dettes.show_dettes),
            ("Clients", ":material/group:", "Clients", clients.show_clients),
            ("Catalogue", ":material/inventory_2:", "Produits & stock", catalogue.show_catalogue),
            ("Entrees", ":material/local_shipping:", "Achats", entrees.show_entrees),
            ("Documents", ":material/receipt_long:", "Ventes & factures", ventes_documents.show_ventes_documents),
            ("Alertes", ":material/notifications:", "Alertes", alertes.show_alertes),
            ("Paramètres", ":material/settings:", "Paramètres", parametres.show_parametres),
        ],
    ),
]
# Anciennes adresses de pages (liens internes, alertes) redirigées vers les pages actuelles
ALIAS = {"Produits": "Catalogue", "Base": "Paramètres", "Aide": "Accueil"}
PAGES = {cle: fn for _, items in MENU for cle, _, _, fn in items}

page = ALIAS.get(st.session_state.get("page", "Accueil"), st.session_state.get("page", "Accueil"))
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
    for _, items in MENU:
        for cle, icone, libelle, _ in items:
            st.button(  # on_click : la page change avant la relance, sans 2e chargement
                libelle,
                key=f"menu_{cle}",
                icon=icone,
                width="stretch",
                type="primary" if cle == page else "secondary",
                on_click=config.aller_vers,
                args=(cle,),
            )
    # Pastilles rouges des compteurs (alertes à traiter, dettes en retard)
    pastilles = {"Alertes": compte[A.CRITIQUE] + compte[A.ATTENTION], "Dettes": compte["dette_retard"]}
    st.markdown(
        "<style>"
        + "".join(
            f".st-key-menu_{k} button::after{{content:'{v}';margin-left:auto;background:#ef4444;color:#fff;"
            "font-size:.72rem;font-weight:700;min-width:20px;height:20px;border-radius:999px;display:grid;"
            "place-items:center;padding:0 6px}"
            for k, v in pastilles.items()
            if v
        )
        + "</style>",
        unsafe_allow_html=True,
    )
    st.markdown(ui.pied_menu(params["boutique_nom"]), unsafe_allow_html=True)
    auth.bouton_deconnexion()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon=":material/check_circle:")

PAGES[page]()
