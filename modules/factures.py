import config
import pandas as pd
import streamlit as st

from config import fmt_money
from db.models import get_session, Vente
from db.utils import get_params
from db import dettes as D
from modules.pdf_utils import generer_facture


def show_factures():
    st.markdown("<h2 style='color: #1e3a8a;'>📄 Factures</h2>", unsafe_allow_html=True)
    params = get_params()
    with get_session() as session:
        ventes = session.query(Vente).order_by(Vente.date.desc()).all()
        if not ventes:
            st.info("Aucune vente enregistrée.")
            return

        def statut(v):
            if v.dette and v.dette.statut != "annulee":
                return D.situation_dette(v.dette)["statut"]
            return "Payée"

        col1, col2 = st.columns(2)
        with col1:
            filtre = st.radio("Afficher", ["Toutes", "Impayées", "Payées"], horizontal=True)
            if filtre == "Impayées":
                ventes = [v for v in ventes if v.dette and v.dette.reste > 0 and v.dette.statut == "en_cours"]
            elif filtre == "Payées":
                ventes = [v for v in ventes if not (v.dette and v.dette.reste > 0 and v.dette.statut == "en_cours")]
            if not ventes:
                st.info("Aucune facture pour ce filtre.")
                return
            vente = config.choisir("Sélectionner une vente", ventes, lambda v: (
                f"F-{v.id:05d} · {v.client.nom if v.client else '?'} · {v.date.strftime('%d/%m/%Y')} · "
                f"{fmt_money(v.total)} · {statut(v)}"))

        with col2:
            reste = vente.dette.reste if vente.dette and vente.dette.statut == "en_cours" else 0
            couleur = "#fee2e2" if reste else "#dcfce7"
            st.markdown(f"""
                <div style='background-color:{couleur};padding:1rem;border-radius:8px;'>
                    <p style='margin:0'><strong>Client :</strong> {vente.client.nom if vente.client else '?'}</p>
                    <p style='margin:4px 0 0 0'><strong>Date :</strong> {vente.date.strftime('%d/%m/%Y %H:%M')}
                    · <strong>Livraison :</strong> {vente.mode_livraison}</p>
                    <p style='margin:4px 0 0 0'><strong>Total :</strong> {fmt_money(vente.total)}
                    · <strong>Reste à payer :</strong> {fmt_money(reste)} · <strong>{statut(vente)}</strong></p>
                </div>""", unsafe_allow_html=True)

        st.markdown("### Détails")
        st.dataframe(pd.DataFrame([{
            "Produit": vp.produit.nom if vp.produit else "Produit inconnu",
            "Prix unitaire": fmt_money(vp.prix_unit), "Quantité": vp.quantite,
            "Total": fmt_money(vp.prix_unit * vp.quantite),
        } for vp in vente.produits]), hide_index=True, use_container_width=True)
        if vente.remise:
            st.caption(f"Remise : {fmt_money(vente.remise)}")
        if reste:
            st.info("Pour encaisser un remboursement, allez dans 💳 Dettes.")

        st.download_button("📥 Télécharger la facture PDF", data=generer_facture(vente, params),
                           file_name=f"Facture_F-{vente.id:05d}.pdf", mime="application/pdf",
                           use_container_width=True)
