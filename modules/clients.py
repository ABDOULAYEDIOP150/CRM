import streamlit as st
import pandas as pd
from db.models import get_session, Client

session = get_session()

def show_clients():
    st.markdown("<h2 style='color: #1e3a8a;'>👥 Gestion des clients</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.container():
            st.markdown("### ➕ Nouveau client")
            with st.form("form_client"):
                nom = st.text_input("Nom complet")
                tel = st.text_input("Téléphone")
                email = st.text_input("Email")
                submitted = st.form_submit_button("Ajouter le client")
                if submitted and nom and tel:
                    if session.query(Client).filter_by(nom=nom, telephone=tel).first():
                        st.error("❌ Ce client existe déjà")
                    else:
                        session.add(Client(nom=nom, telephone=tel, email=email))
                        session.commit()
                        st.success("✅ Client ajouté avec succès")
    
    with col2:
        st.markdown("### 📋 Liste des clients")
        clients = session.query(Client).all()
        if clients:
            df = pd.DataFrame([{
                "ID": c.id,
                "Nom": c.nom,
                "Téléphone": c.telephone,
                "Email": c.email,
                "Ventes": len(c.ventes),
                "Date inscription": c.date_creation.strftime("%d/%m/%Y")
            } for c in clients])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Aucun client enregistré")