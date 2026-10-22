"""Ventes & documents : historique des ventes, réimpression des factures, reconnaissances de dette et reçus."""

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db import dettes as D
from db.models import Vente, get_session
from db.utils import get_params
from modules import documents


def _statut(v):
    if v.dette and v.dette.statut != "annulee":
        return D.situation_dette(v.dette)["statut"]
    return "Payée"


def show_ventes_documents():
    params = get_params()
    config.entete(
        "Ventes & documents", "Retrouvez une vente pour réimprimer sa facture, sa reconnaissance de dette ou ses reçus."
    )
    f1, f2, f3 = st.columns([2, 2, 3])
    periode = f1.date_input("Période", value=(date.today() - timedelta(days=30), date.today()), format="DD/MM/YYYY")
    reglement = f2.selectbox("Règlement", ["Toutes", "Comptant", "À crédit", "Crédit non soldé"])
    recherche = f3.text_input("Client ou produit", placeholder="🔎  Rechercher…")
    if not isinstance(periode, (list, tuple)) or len(periode) != 2:
        st.caption("Choisissez une date de début et une date de fin.")
        return
    debut, fin = datetime.combine(periode[0], time.min), datetime.combine(periode[1], time.max)

    with get_session() as session:
        ventes = session.query(Vente).filter(Vente.date.between(debut, fin)).order_by(Vente.date.desc()).all()
        if reglement == "Comptant":
            ventes = [v for v in ventes if not v.dette]
        elif reglement == "À crédit":
            ventes = [v for v in ventes if v.dette]
        elif reglement == "Crédit non soldé":
            ventes = [v for v in ventes if v.dette and v.dette.statut == "en_cours" and v.dette.reste > 0]
        if recherche:
            r = recherche.lower()
            ventes = [
                v
                for v in ventes
                if r in (v.client.nom + " " + " ".join(vp.produit.nom for vp in v.produits if vp.produit)).lower()
            ]

        config.kpis(
            [
                ("Ventes", len(ventes), config.SECONDARY_BLUE, ""),
                ("Chiffre d'affaires", fmt_money(sum(v.total for v in ventes)), config.SUCCESS_GREEN, ""),
                ("Dont à crédit", fmt_money(sum(v.total for v in ventes if v.dette)), config.WARNING_ORANGE, ""),
            ]
        )
        st.write("")
        if not ventes:
            st.info("Aucune vente pour ces critères.")
            return
        df = pd.DataFrame(
            [
                {
                    "Facture": f"F-{v.id:05d}",
                    "Date": v.date.strftime("%d/%m/%Y %H:%M"),
                    "Client": v.client.nom,
                    "Produits": ", ".join(f"{vp.quantite}× {vp.produit.nom}" for vp in v.produits if vp.produit),
                    "Total": v.total,
                    "Reste dû": v.dette.reste if v.dette and v.dette.statut == "en_cours" else 0,
                    "Statut": _statut(v),
                }
                for v in ventes
            ]
        )
        st.caption("👆 Cliquez sur une vente pour obtenir ses documents.")
        event = st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="table_ventes",
            column_config={k: st.column_config.NumberColumn(format="localized") for k in ["Total", "Reste dû"]},
        )
        st.download_button(
            "⬇️ Exporter la liste (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "ventes.csv", "text/csv"
        )

        if event.selection.rows:
            v = ventes[event.selection.rows[0]]
            st.divider()
            st.markdown(f"### Facture F-{v.id:05d} · {v.client.nom} · {fmt_money(v.total)}")
            b = st.columns(3)
            b[0].download_button(
                "📄 Facture",
                documents.facture(v, params),
                f"Facture_F-{v.id:05d}.pdf",
                "application/pdf",
                type="primary",
                use_container_width=True,
            )
            if v.dette:
                b[1].download_button(
                    "✍️ Reconnaissance de dette",
                    documents.reconnaissance_dette(v.dette, params),
                    f"Reconnaissance_dette_D-{v.dette.id:05d}.pdf",
                    "application/pdf",
                    use_container_width=True,
                )
                if b[2].button("💳 Ouvrir la dette", use_container_width=True):
                    config.aller_a("Dettes", dette_ouverte=v.dette.id)
                for p in v.dette.paiements:
                    st.download_button(
                        f"🧾 Reçu R-{p.id:05d} · {fmt_money(p.montant)} · {p.date.strftime('%d/%m/%Y')}",
                        documents.recu(p, params),
                        f"Recu_R-{p.id:05d}.pdf",
                        "application/pdf",
                        key=f"r_{p.id}",
                    )
