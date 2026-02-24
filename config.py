# config.py
import streamlit as st
from datetime import datetime, timedelta

# Paramètres généraux
APP_NAME = "CRM Professionnel"
APP_ICON = "💼"
LAYOUT = "wide"
SEUIL_STOCK = 2

# Couleurs
PRIMARY_BLUE = "#1e3a8a"
SECONDARY_BLUE = "#2563eb"
LIGHT_BLUE = "#dbeafe"
BACKGROUND_BLUE = "#f0f7ff"
SUCCESS_GREEN = "#10b981"
WARNING_ORANGE = "#f59e0b"
DANGER_RED = "#ef4444"

# CSS Streamlit (optionnel, vous avez déjà un fichier static/styles.css)
STYLES = f"""
<style>
.stApp {{ background-color: {BACKGROUND_BLUE}; }}
h1, h2, h3 {{ color: {PRIMARY_BLUE} !important; }}
.stButton > button {{
    background-color: {SECONDARY_BLUE}; 
    color: white; 
    border-radius: 8px;
}}
.stButton > button:hover {{
    background-color: {PRIMARY_BLUE};
}}
.stat-card {{
    background-color: white;
    padding: 1.5rem;
    border-radius: 15px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    border-left: 4px solid {SECONDARY_BLUE};
    margin-bottom: 1rem;
}}
.stat-title {{
    color: #64748b;
    font-size: 0.9rem;
    text-transform: uppercase;
}}
.stat-value {{
    color: {PRIMARY_BLUE};
    font-size: 2rem;
    font-weight: 700;
}}
.positive {{ color: {SUCCESS_GREEN}; }}
.negative {{ color: {DANGER_RED}; }}
</style>
"""

# Fonction de configuration de la page
def setup_page():
    """Configure la page Streamlit avec les paramètres de base"""
    st.set_page_config(
        page_title=f"{APP_NAME} - Teamleader Style",
        page_icon=APP_ICON,
        layout=LAYOUT,
        initial_sidebar_state="collapsed"
    )

# Fonction pour appliquer le CSS
def apply_styles():
    """Applique les styles CSS à l'application"""
    st.markdown(STYLES, unsafe_allow_html=True)

# Fonctions utilitaires de dates (pour compatibilité)
def get_date_range(periode):
    """
    Retourne une date de début et fin selon la période
    """
    maintenant = datetime.now()
    
    if periode == "Aujourd'hui":
        debut = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = maintenant
    elif periode == "Cette semaine":
        debut = maintenant - timedelta(days=maintenant.weekday())
        debut = debut.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = maintenant
    elif periode == "Ce mois":
        debut = maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin = maintenant
    elif periode == "Cette année":
        debut = maintenant.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        fin = maintenant
    else:  # Personnalisé ou défaut
        debut = maintenant - timedelta(days=30)
        debut = debut.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = maintenant
    
    return debut, fin

# Pour faciliter l'accès
__all__ = [
    'APP_NAME', 'APP_ICON', 'LAYOUT', 'SEUIL_STOCK',
    'PRIMARY_BLUE', 'SECONDARY_BLUE', 'LIGHT_BLUE', 
    'BACKGROUND_BLUE', 'SUCCESS_GREEN', 'WARNING_ORANGE', 'DANGER_RED',
    'STYLES', 'setup_page', 'apply_styles', 'get_date_range'
]