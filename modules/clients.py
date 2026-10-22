import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db import dettes as D
from db.models import Client, get_session


def show_clients():
    st.markdown("<h2 style='color: #1e3a8a;'>👥 Gestion des clients</h2>", unsafe_allow_html=True)
    with get_session() as session:
        col1, col2 = st.columns([2, 3])
        with col1:
            _formulaire(session)
        with col2:
            _liste(session)


def _formulaire(session):
    clients = session.query(Client).order_by(Client.nom).all()
    choix = config.choisir("Client", clients, lambda c: f"✏️ {c.nom} ({c.telephone})", nouveau="➕ Nouveau client")
    c = choix
    with st.form("form_client", clear_on_submit=c is None):
        nom = st.text_input("Nom complet *", value=c.nom if c else "")
        tel = st.text_input("Téléphone *", value=c.telephone if c else "", placeholder="77 123 45 67")
        email = st.text_input("Email", value=(c.email or "") if c else "")
        adresse = st.text_input("Adresse / quartier", value=(c.adresse or "") if c else "")
        plafond = st.number_input(
            "Plafond de crédit (FCFA, 0 = sans limite)",
            min_value=0,
            step=5000,
            value=int(c.plafond_credit or 0) if c else 0,
            help="Montant maximum de dette autorisé pour ce client",
        )
        notes = st.text_area("Notes", value=(c.notes or "") if c else "", height=80)
        if st.form_submit_button("Enregistrer", use_container_width=True):
            if not nom or not tel:
                st.error("Le nom et le téléphone sont obligatoires.")
                return
            doublon = session.query(Client).filter_by(telephone=tel).first()
            if doublon and (c is None or doublon.id != c.id):
                st.error(f"❌ Ce numéro appartient déjà à {doublon.nom}.")
                return
            if c is None:
                c = Client()
                session.add(c)
            c.nom, c.telephone, c.email, c.adresse, c.plafond_credit, c.notes = nom, tel, email, adresse, plafond, notes
            session.commit()
            st.session_state["flash"] = f"✅ Client {nom} enregistré."
            st.rerun()

    if c is not None and not c.ventes and not c.dettes:
        if st.button("🗑️ Supprimer ce client", use_container_width=True):
            session.delete(c)
            session.commit()
            st.rerun()


def _liste(session):
    st.markdown("### 📋 Liste des clients")
    recherche = st.text_input("Rechercher", placeholder="Nom, téléphone, quartier…", label_visibility="collapsed")
    clients = session.query(Client).order_by(Client.nom).all()
    if recherche:
        r = recherche.lower()
        clients = [c for c in clients if r in f"{c.nom} {c.telephone} {c.adresse or ''}".lower()]
    if not clients:
        st.info("Aucun client trouvé")
        return
    df = pd.DataFrame(
        [
            {
                "Nom": c.nom,
                "Téléphone": c.telephone,
                "Adresse": c.adresse or "",
                "Achats": len(c.ventes),
                "Total acheté": sum(v.total for v in c.ventes),
                "Dette en cours": D.encours_client(session, c.id),
                "En retard": "🔴" if D.client_en_retard(session, c.id) else "",
                "Client depuis": c.date_creation.strftime("%d/%m/%Y") if c.date_creation else "",
            }
            for c in clients
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%d FCFA") for c in ["Total acheté", "Dette en cours"]},
    )
    st.caption(f"{len(df)} client(s) · Dettes totales : {fmt_money(df['Dette en cours'].sum())}")
    st.download_button(
        "⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "clients.csv", "text/csv"
    )
