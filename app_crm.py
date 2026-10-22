from datetime import datetime
from pathlib import Path

import streamlit as st

import config
from db.models import init_db, get_session
from db.utils import get_params
from db import dettes as D
from modules import dashboard, clients, produits, ventes, dettes, factures, historique, parametres

config.setup_page()
init_db()
params = get_params()
config.DEVISE = params["devise"]

if "menu_choice" not in st.session_state:
    st.session_state.menu_choice = "Dashboard"

css = Path(__file__).parent / "static" / "styles.css"
st.markdown(f"<style>{css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# Nombre de dettes en retard -> badge dans le menu
with get_session() as s:
    nb_retards = len(D.resume_creances(s, jours_alerte=int(params["jours_alerte_echeance"]))["retards"])

col_menu, col_content = st.columns([1, 7])

with col_menu:
    st.markdown(f"<div style='padding:1rem 0;'><h3 style='color:#1e3a8a;margin-bottom:0.2rem;'>CRM Pro</h3>"
                f"<small style='color:#64748b'>{params['boutique_nom']}</small></div>", unsafe_allow_html=True)
    menu_items = [
        ("📊", "Dashboard"), ("👥", "Clients"), ("📦", "Produits"), ("🛒", "Ventes"),
        ("💳", "Dettes"), ("📄", "Factures"), ("📈", "Historique"), ("⚙️", "Paramètres"),
    ]
    for icon, label in menu_items:
        badge = f" 🔴{nb_retards}" if label == "Dettes" and nb_retards else ""
        if st.session_state.menu_choice == label:
            st.markdown(f"<div style='background-color:#1e3a8a;color:white;padding:10px 14px;border-radius:10px;"
                        f"margin:4px 0;font-weight:500;'>{icon} {label}{badge}</div>", unsafe_allow_html=True)
        elif st.button(f"{icon} {label}{badge}", key=f"menu_{label}", use_container_width=True):
            st.session_state.menu_choice = label
            st.rerun()

with col_content:
    st.markdown(f"""
        <div style='margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid #e2e8f0;
                    display:flex;align-items:center;justify-content:space-between;'>
            <h1 style='font-size:1.5rem;font-weight:600;color:#0f172a;margin:0;'>
                <span style='color:#1e3a8a;'>CRM Pro</span>
                <span style='color:#64748b;font-size:1rem;margin-left:8px;'>/ {st.session_state.menu_choice}</span>
            </h1>
            <span style='color:#64748b;font-size:0.9rem;'>{datetime.now().strftime('%d/%m/%Y')}</span>
        </div>""", unsafe_allow_html=True)

    # Message de confirmation après une action (survit au st.rerun)
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    pages = {
        "Dashboard": dashboard.show_dashboard,
        "Clients": clients.show_clients,
        "Produits": produits.show_produits,
        "Ventes": ventes.show_ventes,
        "Dettes": dettes.show_dettes,
        "Factures": factures.show_factures,
        "Historique": historique.show_historique,
        "Paramètres": parametres.show_parametres,
    }
    pages[st.session_state.menu_choice]()
