import streamlit as st

import config
from db.utils import get_params, set_params


def show_parametres():
    st.markdown("<h2 style='color: #1e3a8a;'>⚙️ Paramètres de la boutique</h2>", unsafe_allow_html=True)
    st.caption("Ces informations apparaissent sur les factures, les reçus et les messages de relance. "
               "Chaque boutique qui utilise l'application peut les adapter.")
    p = get_params()
    with st.form("parametres"):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom de la boutique", p["boutique_nom"])
            adresse = st.text_input("Adresse", p["boutique_adresse"])
            tel = st.text_input("Téléphone (Wave / Orange Money)", p["boutique_telephone"])
            email = st.text_input("Email", p["boutique_email"])
        with c2:
            ninea = st.text_input("NINEA", p["boutique_ninea"])
            rccm = st.text_input("RCCM", p["boutique_rccm"])
            seuil = st.number_input("Seuil d'alerte stock", min_value=0, value=int(p["seuil_stock"]))
            jours = st.number_input("Alerter X jours avant une échéance", min_value=0, max_value=30,
                                    value=int(p["jours_alerte_echeance"]))
        msg = st.text_area("Modèle du message de relance", p["message_relance"], height=110,
                           help="Variables : {client} {reste} {echeance} {boutique} {telephone}")
        if st.form_submit_button("💾 Enregistrer", use_container_width=True):
            set_params({"boutique_nom": nom, "boutique_adresse": adresse, "boutique_telephone": tel,
                        "boutique_email": email, "boutique_ninea": ninea, "boutique_rccm": rccm,
                        "seuil_stock": seuil, "jours_alerte_echeance": jours, "message_relance": msg})
            st.session_state["flash"] = "✅ Paramètres enregistrés."
            st.rerun()
    if st.button("Rétablir le message de relance par défaut"):
        set_params({"message_relance": config.PARAMETRES_DEFAUT["message_relance"]})
        st.rerun()
