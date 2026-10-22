# config.py
import streamlit as st
from datetime import datetime, timedelta

# ========== Paramètres généraux ==========
APP_NAME = "CRM Professionnel"
APP_ICON = "💼"
LAYOUT = "wide"

# Valeurs par défaut (modifiables dans la page ⚙️ Paramètres, stockées en base)
SEUIL_STOCK = 2                 # alerte stock faible
DEVISE = "FCFA"                 # Franc CFA (XOF) — pas de centimes
JOURS_ALERTE_ECHEANCE = 3       # alerte X jours avant une échéance

PARAMETRES_DEFAUT = {
    "boutique_nom": "Ma Boutique",
    "boutique_adresse": "Dakar, Sénégal",
    "boutique_telephone": "+221 77 000 00 00",
    "boutique_email": "",
    "boutique_ninea": "",
    "boutique_rccm": "",
    "devise": DEVISE,
    "seuil_stock": str(SEUIL_STOCK),
    "jours_alerte_echeance": str(JOURS_ALERTE_ECHEANCE),
    "message_relance": (
        "Bonjour {client}, ceci est un rappel amical de {boutique} : "
        "il reste {reste} à régler. Prochaine échéance : {echeance}. "
        "Paiement possible par Wave ou Orange Money au {telephone}. Merci !"
    ),
}

# Moyens de paiement courants au Sénégal
MODES_PAIEMENT = ["Espèces", "Wave", "Orange Money", "Free Money", "Carte bancaire", "Virement", "Chèque"]

# Fréquences de remboursement d'une dette
FREQUENCES = {
    "Hebdomadaire": {"jours": 7},
    "Toutes les 2 semaines": {"jours": 14},
    "Mensuelle": {"mois": 1},
}

# ========== Couleurs ==========
PRIMARY_BLUE = "#1e3a8a"
SECONDARY_BLUE = "#2563eb"
LIGHT_BLUE = "#dbeafe"
BACKGROUND_BLUE = "#f0f7ff"
SUCCESS_GREEN = "#10b981"
WARNING_ORANGE = "#f59e0b"
DANGER_RED = "#ef4444"

STYLES = f"""
<style>
.stApp {{ background-color: {BACKGROUND_BLUE}; }}
h1, h2, h3 {{ color: {PRIMARY_BLUE} !important; }}
.stButton > button {{
    background-color: {SECONDARY_BLUE};
    color: white;
    border-radius: 8px;
}}
.stButton > button:hover {{ background-color: {PRIMARY_BLUE}; }}
.positive {{ color: {SUCCESS_GREEN}; }}
.negative {{ color: {DANGER_RED}; }}
</style>
"""


def setup_page():
    """Configure la page Streamlit avec les paramètres de base"""
    st.set_page_config(
        page_title=APP_NAME,
        page_icon=APP_ICON,
        layout=LAYOUT,
        initial_sidebar_state="collapsed",
    )


def apply_styles():
    st.markdown(STYLES, unsafe_allow_html=True)


# ========== Formatage ==========
def fmt_money(montant, devise=None):
    """Formate un montant en FCFA : 12500 -> '12 500 FCFA' (pas de décimales)."""
    devise = devise or DEVISE
    try:
        valeur = round(float(montant or 0))
    except (TypeError, ValueError):
        valeur = 0
    return f"{valeur:,}".replace(",", " ") + f" {devise}"


def fmt_date(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def get_date_range(periode):
    """Retourne une date de début et fin selon la période"""
    maintenant = datetime.now()
    if periode == "Aujourd'hui":
        debut = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periode == "Cette semaine":
        debut = (maintenant - timedelta(days=maintenant.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periode == "Ce mois":
        debut = maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif periode == "Cette année":
        debut = maintenant.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # 30 derniers jours
        debut = (maintenant - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    return debut, maintenant


def stat_card(titre, valeur, couleur=SECONDARY_BLUE, sous_titre=""):
    """HTML d'une carte KPI."""
    sub = f"<div style='color:#64748b;font-size:0.8rem;margin-top:4px;'>{sous_titre}</div>" if sous_titre else ""
    return f"""
        <div class="stat-card" style="border-left:4px solid {couleur};">
            <div class="stat-title">{titre}</div>
            <div class="stat-value" style="font-size:1.6rem;">{valeur}</div>{sub}
        </div>
    """


def choisir(label, objets, libelle, nouveau=None, **kwargs):
    """selectbox sur des objets SQLAlchemy : le widget ne mémorise que les IDs (les objets d'une session
    fermée ne doivent pas être réutilisés au rerun suivant). `nouveau` = libellé d'une option « aucun »."""
    par_id = {o.id: o for o in objets}
    ids = ([None] if nouveau else []) + list(par_id)
    choix = st.selectbox(label, ids, format_func=lambda i: nouveau if i is None else libelle(par_id[i]), **kwargs)
    if choix not in par_id and not nouveau and objets:
        return objets[0]
    return par_id.get(choix)
