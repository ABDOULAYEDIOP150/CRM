import streamlit as st
import pandas as pd
from datetime import datetime
from db.models import get_session, Client, Produit, Vente, VenteProduit, HistoriqueVente

session = get_session()

def show_ventes():
    st.markdown("<h2 style='color: #1e3a8a;'>🛒 Nouvelle vente</h2>", unsafe_allow_html=True)
    
    clients = session.query(Client).all()
    if not clients:
        st.warning("⚠️ Ajoutez d'abord des clients pour effectuer des ventes")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            with st.container():
                st.markdown("### Sélection client")
                client_options = [f"{c.id} - {c.nom} ({c.telephone})" for c in clients]
                client_sel = st.selectbox("Choisir un client", client_options)
                client_id = int(client_sel.split(" - ")[0])
                client = session.query(Client).get(client_id)
                
                if client:
                    st.markdown(f"""
                        <div style='background-color: #dbeafe; padding: 1rem; border-radius: 8px; margin-top: 1rem;'>
                            <p><strong>Client sélectionné:</strong> {client.nom}</p>
                            <p><strong>Tel:</strong> {client.telephone}</p>
                            <p><strong>Email:</strong> {client.email or 'Non renseigné'}</p>
                        </div>
                    """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("### Mode de livraison")
            mode = st.radio("", ["Livraison à domicile", "Retrait en magasin"], horizontal=True)
            
            st.markdown("### Recherche produit")
            produit_recherche = st.text_input("Nom du produit", placeholder="Ex: Ordinateur...")
        
        if "panier" not in st.session_state:
            st.session_state["panier"] = {}
        
        if produit_recherche:
            produits_trouves = session.query(Produit).filter(
                Produit.nom.ilike(f"%{produit_recherche}%"), 
                Produit.stock > 0
            ).all()
            
            if produits_trouves:
                st.markdown("### Résultats de recherche")
                cols = st.columns(3)
                for i, p in enumerate(produits_trouves):
                    with cols[i % 3]:
                        with st.container():
                            st.markdown(f"""
                                <div style='border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                                    <h4 style='margin: 0; color: #1e3a8a;'>{p.nom}</h4>
                                    <p style='margin: 5px 0;'><strong>Prix:</strong> {p.prix:.2f} EUR</p>
                                    <p style='margin: 0;'><strong>Stock:</strong> {p.stock}</p>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            qty = st.number_input(
                                "Quantité", 
                                min_value=1, 
                                max_value=p.stock, 
                                step=1,
                                key=f"qty_{p.id}"
                            )
                            
                            if st.button(f"➕ Ajouter au panier", key=f"add_{p.id}"):
                                if p.id not in st.session_state["panier"]:
                                    st.session_state["panier"][p.id] = {
                                        "produit": p,
                                        "quantite": qty
                                    }
                                    st.success(f"✅ {p.nom} ajouté au panier")
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ {p.nom} déjà dans le panier")
            else:
                st.info("Aucun produit trouvé")
        
        if st.session_state["panier"]:
            st.markdown("---")
            st.markdown("### 🛍️ Panier actuel")
            
            panier_data = []
            total_panier = 0
            for item in st.session_state["panier"].values():
                produit = item["produit"]
                quantite = item["quantite"]
                total_ligne = produit.prix * quantite
                total_panier += total_ligne
                panier_data.append({
                    "Produit": produit.nom,
                    "Prix unitaire": f"{produit.prix:.2f} EUR",
                    "Quantité": quantite,
                    "Total": f"{total_ligne:.2f} EUR"
                })
            
            df_panier = pd.DataFrame(panier_data)
            st.dataframe(df_panier, use_container_width=True)
            
            st.markdown(f"""
                <div style='background-color: #1e3a8a; color: white; padding: 1rem; border-radius: 8px; margin-top: 1rem;'>
                    <h3 style='margin: 0; color: white;'>Total: {total_panier:.2f} EUR</h3>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("✅ Valider la vente", use_container_width=True):
                    vente = Vente(client=client, mode_livraison=mode)
                    session.add(vente)
                    session.commit()
                    
                    for item in st.session_state["panier"].values():
                        prod = item["produit"]
                        qty = item["quantite"]
                        vp = VenteProduit(
                            vente_id=vente.id, 
                            produit_id=prod.id, 
                            quantite=qty, 
                            prix_unit=prod.prix
                        )
                        prod.stock -= qty
                        session.add(vp)
                        
                        hist = HistoriqueVente(
                            vente_id=vente.id,
                            client_nom=client.nom,
                            client_telephone=client.telephone,
                            produit_nom=prod.nom,
                            quantite=qty,
                            prix_unit=prod.prix,
                            date=datetime.now()
                        )
                        session.add(hist)
                    
                    session.commit()
                    st.success("✅ Vente enregistrée avec succès !")
                    st.balloons()
                    st.session_state["panier"] = {}
                    st.rerun()
            
            with col3:
                if st.button("🗑️ Vider le panier", use_container_width=True):
                    st.session_state["panier"] = {}
                    st.rerun()