import streamlit as st
import pandas as pd
from fpdf import FPDF
from db.models import get_session, Vente

session = get_session()

class PDF(FPDF):
    def header(self):
        self.set_fill_color(30, 58, 138)
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 28)
        self.cell(0, 30, "CRM PRO", ln=True, align="C")
        self.ln(10)

def generer_pdf(vente):
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 22)
    pdf.cell(0, 10, "FACTURE", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(100, 8, "Entreprise CRM Pro", ln=0)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Date: {vente.date.strftime('%d/%m/%Y')}", ln=1, align="R")
    
    pdf.cell(100, 8, "123 Avenue des Affaires", ln=0)
    pdf.cell(0, 8, f"Facture N°: F-{vente.id:04d}", ln=1, align="R")
    
    pdf.cell(100, 8, "contact@crmpro.com", ln=1)
    pdf.ln(15)
    
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "FACTURER A", ln=True, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    
    client_nom = vente.client.nom if vente.client else "Client supprimé"
    client_tel = vente.client.telephone if vente.client else ""
    client_email = vente.client.email if vente.client else ""
    
    pdf.cell(0, 8, f"Client: {client_nom}", ln=True)
    pdf.cell(0, 8, f"Téléphone: {client_tel}", ln=True)
    pdf.cell(0, 8, f"Email: {client_email}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(70, 12, "Produit", border=1, fill=True)
    pdf.cell(30, 12, "Prix Unit.", border=1, fill=True)
    pdf.cell(30, 12, "Quantité", border=1, fill=True)
    pdf.cell(40, 12, "Total", border=1, fill=True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 12)
    total_general = 0
    
    if vente.produits and len(vente.produits) > 0:
        for vp in vente.produits:
            prix = vp.prix_unit
            quantite = vp.quantite
            total = prix * quantite
            total_general += total
            
            nom_produit = vp.produit.nom if vp.produit else "Produit inconnu"
            if len(nom_produit) > 30:
                nom_produit = nom_produit[:27] + "..."
            
            pdf.cell(70, 10, nom_produit, border=1)
            pdf.cell(30, 10, f"{prix:.2f} EUR", border=1, align="R")
            pdf.cell(30, 10, str(quantite), border=1, align="C")
            pdf.cell(40, 10, f"{total:.2f} EUR", border=1, align="R")
            pdf.ln()
    else:
        pdf.cell(170, 10, "Aucun produit dans cette facture", border=1, align="C")
        pdf.ln()
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 14)
    pdf.set_fill_color(219, 234, 254)
    pdf.cell(130, 12, "", fill=True)
    pdf.cell(30, 12, "TOTAL TTC:", border=1, fill=True)
    pdf.cell(40, 12, f"{total_general:.2f} EUR", border=1, fill=True, align="R")
    pdf.ln(20)
    
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(0, 8, "Merci pour votre confiance !", ln=True, align="C")
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, "CRM Pro - Solution de gestion professionnelle", ln=True, align="C")
    
    return pdf.output(dest="S").encode("latin-1", errors="replace")

def show_factures():
    st.markdown("<h2 style='color: #1e3a8a;'>📄 Génération de factures</h2>", unsafe_allow_html=True)
    
    ventes = session.query(Vente).order_by(Vente.date.desc()).all()
    if ventes:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            vente_options = [f"{v.id} - {v.client.nom} - {v.date.strftime('%d/%m/%Y')}" for v in ventes]
            sel = st.selectbox("Sélectionner une vente", vente_options)
            vid = int(sel.split(" - ")[0])
            vente = session.query(Vente).get(vid)
        
        with col2:
            if vente:
                st.markdown(f"""
                    <div style='background-color: #dbeafe; padding: 1rem; border-radius: 8px;'>
                        <p><strong>Client:</strong> {vente.client.nom}</p>
                        <p><strong>Date:</strong> {vente.date.strftime('%d/%m/%Y %H:%M')}</p>
                        <p><strong>Mode:</strong> {vente.mode_livraison}</p>
                    </div>
                """, unsafe_allow_html=True)
        
        if vente:
            st.markdown("### Détails de la facture")
            if vente.produits and len(vente.produits) > 0:
                details = []
                for vp in vente.produits:
                    details.append({
                        "Produit": vp.produit.nom if vp.produit else "Produit inconnu",
                        "Prix unitaire": f"{vp.prix_unit:.2f} EUR",
                        "Quantité": vp.quantite,
                        "Total": f"{vp.prix_unit * vp.quantite:.2f} EUR"
                    })
                
                df_details = pd.DataFrame(details)
                st.dataframe(df_details, use_container_width=True)
            else:
                st.warning("⚠️ Cette vente n'a aucun produit associé")
            
            pdf_data = generer_pdf(vente)
            
            st.download_button(
                label="📥 Télécharger la facture PDF",
                data=pdf_data,
                file_name=f"Facture_{vente.id:04d}.pdf",
                mime="application/pdf",
                use_container_width=True
            )