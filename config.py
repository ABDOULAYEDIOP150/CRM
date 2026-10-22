"""Paramètres généraux, formatage (FCFA) et petits composants d'interface réutilisés par toutes les pages."""

from datetime import datetime, timedelta
from html import escape

import streamlit as st

APP_NAME = "CRM Pro"
APP_ICON = "💼"

# Valeurs par défaut (modifiables dans Paramètres, stockées en base)
SEUIL_STOCK = 2
DEVISE = "FCFA"
JOURS_ALERTE_ECHEANCE = 2  # alerte X jours avant un paiement prévu
JOURS_STOCK_DORMANT = 30  # produit en stock mais pas vendu depuis X jours

PARAMETRES_DEFAUT = {
    "boutique_nom": "Ma Boutique",
    "boutique_adresse": "Dakar, Sénégal",
    "boutique_telephone": "+221 77 000 00 00",
    "boutique_email": "",
    "boutique_ninea": "",
    "boutique_rccm": "",
    "devise": DEVISE,
    "police": "Inter",
    "marge_defaut": "20",  # % de marge proposé pour le prix de vente lors d'une entrée de stock
    "seuil_stock": str(SEUIL_STOCK),
    "jours_alerte_echeance": str(JOURS_ALERTE_ECHEANCE),
    "jours_stock_dormant": str(JOURS_STOCK_DORMANT),
    "message_relance": (
        "Bonjour {client}, ceci est un rappel amical de {boutique} : "
        "il reste {reste} à régler. Prochaine échéance : {echeance}. "
        "Paiement possible par Wave ou Orange Money au {telephone}. Merci !"
    ),
}

MODES_PAIEMENT = ["Espèces", "Wave", "Orange Money", "Free Money", "Carte bancaire", "Virement", "Chèque"]

FREQUENCES = {
    "Hebdomadaire": {"jours": 7},
    "Toutes les 2 semaines": {"jours": 14},
    "Mensuelle": {"mois": 1},
}

CLIENT_PASSAGE = "Client de passage"

# Polices proposées (Google Fonts) : nom -> description
POLICES = {
    "Inter": "moderne et très lisible (recommandée)",
    "Poppins": "arrondie et chaleureuse",
    "Nunito": "douce et aérée",
    "Montserrat": "élégante, style affiche",
    "Roboto": "classique, style Android",
    "Source Sans 3": "police d'origine de Streamlit",
}
POLICE = "Inter"


def css_police(nom):
    """CSS qui charge la police depuis Google Fonts et l'applique à l'interface (sans casser les icônes)."""
    if nom not in POLICES:
        nom = "Inter"
    url = "https://fonts.googleapis.com/css2?family=" + nom.replace(" ", "+") + ":wght@400;500;600;700;800&display=swap"
    cible = (
        ".stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp h1, "
        ".stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp td, .stApp th, .stApp small, "
        ".stMarkdown, [data-baseweb='select'] div, [data-baseweb='popover'] li, [data-testid='stMetricValue'], "
        ".crm-kpi, .crm-head, .crm-alert, .crm-total, .crm-prod, .crm-prix"
    )
    return f"<style>@import url('{url}'); {cible} {{ font-family: '{nom}', sans-serif !important; }}</style>"


UNITES = [
    "pièce",
    "sac",
    "kg",
    "tonne",
    "m³",
    "barre",
    "mètre",
    "rouleau",
    "litre",
    "seau",
    "boîte",
    "paquet",
    "carton",
    "lot",
]
CATEGORIES_DEFAUT = [
    "Ciment & maçonnerie",
    "Fer & métaux",
    "Plomberie",
    "Électricité",
    "Peinture",
    "Quincaillerie générale",
    "Outillage",
    "Alimentation",
    "Divers",
]


# Couleurs
PRIMARY_BLUE = "#1e3a8a"
SECONDARY_BLUE = "#2563eb"
SUCCESS_GREEN = "#059669"
WARNING_ORANGE = "#d97706"
DANGER_RED = "#dc2626"
MUTED = "#64748b"


def setup_page():
    st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="wide", initial_sidebar_state="expanded")


# ---------------------------------------------------------------- Formatage
def fmt_money(montant, devise=None):
    """12500 -> '12 500 FCFA'."""
    devise = devise or DEVISE
    try:
        valeur = round(float(montant or 0))
    except (TypeError, ValueError):
        valeur = 0
    return f"{valeur:,}".replace(",", " ") + f" {devise}"


def fmt_date(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def get_date_range(periode):
    maintenant = datetime.now()
    minuit = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    if periode == "Aujourd'hui":
        debut = minuit
    elif periode == "Cette semaine":
        debut = minuit - timedelta(days=maintenant.weekday())
    elif periode == "Ce mois":
        debut = minuit.replace(day=1)
    elif periode == "Cette année":
        debut = minuit.replace(month=1, day=1)
    else:
        debut = minuit - timedelta(days=30)
    return debut, maintenant


# ---------------------------------------------------------------- Composants
def entete(titre, sous_titre=""):
    """Titre de page homogène."""
    sous = f"<p class='crm-sub'>{escape(sous_titre)}</p>" if sous_titre else ""
    st.markdown(f"<div class='crm-head'><h1>{escape(titre)}</h1>{sous}</div>", unsafe_allow_html=True)


def kpi(titre, valeur, couleur=SECONDARY_BLUE, detail=""):
    det = f"<div class='crm-kpi-det'>{escape(str(detail))}</div>" if detail else ""
    return (
        f"<div class='crm-kpi' style='--c:{couleur}'><div class='crm-kpi-t'>{escape(titre)}</div>"
        f"<div class='crm-kpi-v'>{escape(str(valeur))}</div>{det}</div>"
    )


def kpis(liste):
    """Affiche une rangée de cartes KPI : [(titre, valeur, couleur, détail), ...]."""
    cols = st.columns(len(liste))
    for col, item in zip(cols, liste, strict=True):
        col.markdown(kpi(*item), unsafe_allow_html=True)


def badge(texte, couleur):
    return f"<span class='crm-badge' style='--c:{couleur}'>{escape(texte)}</span>"


def choisir(label, objets, libelle, nouveau=None, **kwargs):
    """selectbox sur des objets SQLAlchemy : le widget ne mémorise que les IDs."""
    par_id = {o.id: o for o in objets}
    ids = ([None] if nouveau else []) + list(par_id)
    choix = st.selectbox(label, ids, format_func=lambda i: nouveau if i is None else libelle(par_id[i]), **kwargs)
    if choix not in par_id and not nouveau and objets:
        return objets[0]
    return par_id.get(choix)


def flash(message):
    """Message de confirmation affiché après le prochain rerun."""
    st.session_state["flash"] = message


def aller_a(page, **etat):
    """Change de page (menu latéral) en passant éventuellement des valeurs."""
    st.session_state["page"] = page
    st.session_state.update(etat)
    st.rerun()
