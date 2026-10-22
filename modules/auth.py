"""Connexion par mot de passe (indispensable dès que l'application est en ligne avec un lien public)."""

import hmac
import os

import streamlit as st


def secret(cle, defaut=None):
    """Lit une variable d'environnement, sinon un secret Streamlit, sinon la valeur par défaut."""
    if os.environ.get(cle):
        return os.environ[cle]
    try:
        return st.secrets.get(cle, defaut)
    except Exception:  # pas de fichier secrets.toml
        return defaut


def verifier_acces():
    """Affiche un écran de connexion si APP_PASSWORD est défini. Retourne True si l'accès est autorisé."""
    mot_de_passe = secret("APP_PASSWORD")
    if not mot_de_passe or st.session_state.get("connecte"):
        return True

    _, centre, _ = st.columns([1, 1, 1])
    with centre:
        st.markdown(
            "<h2 style='text-align:center;color:#1e3a8a;margin-top:4rem'>🔐 CRM Pro</h2>", unsafe_allow_html=True
        )
        with st.form("connexion"):
            saisi = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", use_container_width=True):
                if hmac.compare_digest(saisi.encode(), str(mot_de_passe).encode()):
                    st.session_state["connecte"] = True
                    st.rerun()
                st.error("Mot de passe incorrect.")
    return False


def bouton_deconnexion():
    if secret("APP_PASSWORD") and st.button("🚪 Déconnexion", key="logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()
