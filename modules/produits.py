import streamlit as st
import pandas as pd
from db.models import get_session, Produit
import config

session = get_session()

def show_produits():
    st.markdown("<h2 style='color: #1e3a8a;'>📦 Gestion des produits</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.container():
            st.markdown("### ➕ Nouveau produit")
            with st.form("form_produit"):
                nom = st.text_input("Nom du produit")
                prix = st.number_input("Prix (EUR)", min_value=0.0, step=0.5)
                stock = st.number_input("Stock initial", min_value=0, step=1)
                submitted = st.form_submit_button("Ajouter le produit")
                if submitted and nom:
                    if session.query(Produit).filter_by(nom=nom).first():
                        st.error("❌ Ce produit existe déjà")
                    else:
                        session.add(Produit(nom=nom, prix=prix, stock=stock))
                        session.commit()
                        st.success("✅ Produit ajouté avec succès")
    
    with col2:
        st.markdown("### 📋 Inventaire")
        produits = session.query(Produit).all()
        if produits:
            df = pd.DataFrame([{
                "ID": p.id,
                "Produit": p.nom,
                "Prix": f"{p.prix:.2f} EUR",
                "Stock": p.stock,
                "Valeur": f"{p.prix * p.stock:.2f} EUR",
                "Statut": "⚠️ Stock faible" if p.stock <= config.SEUIL_STOCK else "✅ OK"
            } for p in produits])
            st.dataframe(df, use_container_width=True)
            
            alertes = [p.nom for p in produits if p.stock <= config.SEUIL_STOCK]
            if alertes:
                st.markdown(f"""
                    <div style='background-color: #fef9c3; padding: 1rem; border-radius: 8px; margin-top: 1rem;'>
                        <p style='color: #854d0e; margin: 0;'><strong>⚠️ Alertes stock faible</strong></p>
                        <p style='color: #854d0e; margin: 5px 0 0 0;'>{', '.join(alertes)}</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Aucun produit en stock")