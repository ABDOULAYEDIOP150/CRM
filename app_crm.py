import streamlit as st
import config
from db.models import init_db
from modules import dashboard, clients, produits, ventes, factures, historique
from datetime import datetime  # <--- LIGNE AJOUTÉE

# Configuration
config.setup_page()
init_db()

# Initialisation de l'état du menu
if 'menu_choice' not in st.session_state:
    st.session_state.menu_choice = "Dashboard"

# CSS personnalisé
with open("static/styles.css", "r") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ========== STRUCTURE À 2 COLONNES ==========
col_menu, col_content = st.columns([1, 7])  # 1/8 et 7/8

# ========== COLONNE MENU (1/8) ==========
with col_menu:
    st.markdown("""
        <div style='padding: 1rem 0;'>
            <h3 style='color: #1e3a8a; margin-bottom: 2rem;'>CRM Pro</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # Menu items
    menu_items = [
        ("📊", "Dashboard"),
        ("👥", "Clients"),
        ("📦", "Produits"),
        ("🛒", "Ventes"),
        ("📄", "Factures"),
        ("📈", "Historique")
    ]
    
    for icon, label in menu_items:
        # Déterminer si l'item est actif
        is_active = (st.session_state.menu_choice == label)
        
        # Style différent pour actif/inactif
        if is_active:
            st.markdown(f"""
                <div style='
                    background-color: #1e3a8a;
                    color: white;
                    padding: 12px 16px;
                    border-radius: 10px;
                    margin: 4px 0;
                    font-weight: 500;
                    cursor: pointer;
                '>
                    <span style='margin-right: 10px;'>{icon}</span> {label}
                </div>
            """, unsafe_allow_html=True)
        else:
            # Bouton Streamlit pour les items inactifs
            if st.button(f"{icon} {label}", key=f"menu_{label}", use_container_width=True):
                st.session_state.menu_choice = label
                st.rerun()

# ========== COLONNE CONTENU (7/8) ==========
with col_content:
    # Header minimal avec date
    st.markdown(f"""
        <div style='
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
            justify-content: space-between;
        '>
            <h1 style='
                font-size: 1.5rem;
                font-weight: 600;
                color: #0f172a;
                margin: 0;
            '>
                <span style='color: #1e3a8a;'>CRM Pro</span>
                <span style='color: #64748b; font-size: 1rem; margin-left: 8px;'>/ {st.session_state.menu_choice}</span>
            </h1>
            <span style='color: #64748b; font-size: 0.9rem;'>{datetime.now().strftime('%d %B %Y')}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Routage des modules
    if st.session_state.menu_choice == "Dashboard":
        dashboard.show_dashboard()
    elif st.session_state.menu_choice == "Clients":
        clients.show_clients()
    elif st.session_state.menu_choice == "Produits":
        produits.show_produits()
    elif st.session_state.menu_choice == "Ventes":
        ventes.show_ventes()
    elif st.session_state.menu_choice == "Factures":
        factures.show_factures()
    elif st.session_state.menu_choice == "Historique":
        historique.show_historique()