"""Journal des mouvements de stock (onglet de la page Produits & stock)."""

import pandas as pd
import streamlit as st

from db.models import MouvementStock
from modules.tableaux import styliser

TYPES_MVT = ["Vente", "Réception", "Import", "Inventaire", "Correction", "Création"]


def mouvements(session, produits):
    par_id = {p.id: f"{p.reference} · {p.nom}" for p in produits}
    a, b = st.columns([2, 1])
    choix = a.selectbox(
        "Produit",
        [None, *par_id],
        format_func=lambda i: "Tous les produits" if i is None else par_id[i],
        key="mvt_produit",
    )
    types = b.multiselect("Type", TYPES_MVT, placeholder="Tous")
    q = session.query(MouvementStock).order_by(MouvementStock.date.desc(), MouvementStock.id.desc())
    if choix is not None:
        q = q.filter(MouvementStock.produit_id == choix)
    if types:
        q = q.filter(MouvementStock.type.in_(types))
    mvts = q.limit(500).all()
    if not mvts:
        st.info("Aucun mouvement enregistré pour l'instant.")
        return
    df = pd.DataFrame(
        [
            {
                "Date": m.date.strftime("%d/%m/%Y %H:%M"),
                "Code": m.produit.reference,
                "Produit": m.produit.nom,
                "Type": m.type,
                "Quantité": f"{m.quantite:+d} {m.produit.unite or ''}".strip(),
                "Stock après": m.stock_apres,
                "Détail": m.note,
            }
            for m in mvts
        ]
    )
    st.dataframe(styliser(df), hide_index=True, width="stretch")
    st.download_button(
        "Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "mouvements_stock.csv", "text/csv"
    )
