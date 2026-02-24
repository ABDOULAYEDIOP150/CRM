import streamlit as st
import pandas as pd
from db.models import get_session, HistoriqueVente

session = get_session()

def show_historique():
    st.markdown("<h2 style='color: #1e3a8a;'>📊 Historique des ventes</h2>", unsafe_allow_html=True)
    
    hist = session.query(HistoriqueVente).order_by(HistoriqueVente.date.desc()).all()
    if hist:
        df = pd.DataFrame([{
            "Date": h.date.strftime("%d/%m/%Y %H:%M"),
            "ID Vente": h.vente_id,
            "Client": h.client_nom,
            "Téléphone": h.client_telephone,
            "Produit": h.produit_nom,
            "Qté": h.quantite,
            "Prix unitaire": f"{h.prix_unit:.2f} EUR",
            "Total": f"{h.quantite * h.prix_unit:.2f} EUR"
        } for h in hist])
        
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📈 Résumé des ventes")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            total_ventes = len(set([h.vente_id for h in hist]))
            st.metric("Nombre total de ventes", total_ventes)
        
        with col2:
            total_produits = sum([h.quantite for h in hist])
            st.metric("Produits vendus", total_produits)
        
        with col3:
            ca_total = sum([h.quantite * h.prix_unit for h in hist])
            st.metric("Chiffre d'affaires", f"{ca_total:.2f} EUR")
    else:
        st.info("Aucune vente enregistrée dans l'historique")