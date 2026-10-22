from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from config import fmt_money
from db.models import HistoriqueVente, get_session


def show_historique():
    st.markdown("<h2 style='color: #1e3a8a;'>📈 Historique des ventes</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        periode = st.date_input("Période", value=(date.today() - timedelta(days=30), date.today()), format="DD/MM/YYYY")
    with c2:
        recherche = st.text_input("Client ou produit", placeholder="Rechercher…")
    if not isinstance(periode, (list, tuple)) or len(periode) != 2:
        st.caption("Choisissez une date de début et une date de fin.")
        return
    debut, fin = datetime.combine(periode[0], time.min), datetime.combine(periode[1], time.max)

    with get_session() as session:
        hist = (
            session.query(HistoriqueVente)
            .filter(HistoriqueVente.date.between(debut, fin))
            .order_by(HistoriqueVente.date.desc())
            .all()
        )
    if recherche:
        r = recherche.lower()
        hist = [h for h in hist if r in f"{h.client_nom} {h.produit_nom} {h.client_telephone}".lower()]
    if not hist:
        st.info("Aucune vente sur cette période.")
        return

    df = pd.DataFrame(
        [
            {
                "Date": h.date.strftime("%d/%m/%Y %H:%M"),
                "Facture": f"F-{h.vente_id:05d}",
                "Client": h.client_nom,
                "Téléphone": h.client_telephone,
                "Produit": h.produit_nom,
                "Qté": h.quantite,
                "Prix unitaire": h.prix_unit,
                "Total": h.quantite * h.prix_unit,
            }
            for h in hist
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%d FCFA") for c in ["Prix unitaire", "Total"]},
    )
    st.download_button(
        "⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "historique_ventes.csv", "text/csv"
    )

    k1, k2, k3 = st.columns(3)
    k1.metric("Nombre de ventes", len({h.vente_id for h in hist}))
    k2.metric("Produits vendus", sum(h.quantite for h in hist))
    k3.metric("Montant brut (avant remises)", fmt_money(df["Total"].sum()))
