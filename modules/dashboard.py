"""Tableau de bord : chiffres clés, alertes (dettes en retard, échéances, stock) et graphiques."""

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from config import fmt_date, fmt_money
from db import dettes as D
from db.models import Produit, get_session
from db.utils import get_evolution_ca, get_params, get_repartition_paiements, get_stats_periode, get_top_produits

PERIODES = ["Aujourd'hui", "Cette semaine", "Ce mois", "Cette année", "30 derniers jours"]


def _layout(fig, h=290):
    fig.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        height=h,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def show_dashboard():
    params = get_params()
    seuil = int(params["seuil_stock"])
    jours = int(params["jours_alerte_echeance"])
    config.entete("Tableau de bord", params["boutique_nom"])

    a, b, c = st.columns([1.2, 1.2, 4])
    if a.button("🛒 Nouvelle vente", type="primary", use_container_width=True):
        config.aller_a("Ventes")
    if b.button("💰 Encaisser une dette", use_container_width=True):
        config.aller_a("Dettes")
    periode = c.segmented_control("Période", PERIODES, default="Ce mois", label_visibility="collapsed") or "Ce mois"
    debut, fin = config.get_date_range(periode)
    stats = get_stats_periode(debut, fin)

    with get_session() as session:
        r = D.resume_creances(session, jours_alerte=jours)
        faibles = [
            (p.nom, p.stock) for p in session.query(Produit).filter(Produit.stock <= seuil).order_by(Produit.stock)
        ]
        config.kpis(
            [
                (
                    "Chiffre d'affaires",
                    fmt_money(stats["ca_total"]),
                    config.SECONDARY_BLUE,
                    f"{stats['nb_ventes']} vente(s)",
                ),
                ("Argent encaissé", fmt_money(stats["encaisse"]), config.SUCCESS_GREEN, "ventes comptant + versements"),
                (
                    "Dettes à encaisser",
                    fmt_money(r["total_du"]),
                    config.WARNING_ORANGE,
                    f"{r['nb_debiteurs']} client(s)",
                ),
                ("Dont en retard", fmt_money(r["montant_retard"]), config.DANGER_RED, f"{len(r['retards'])} dette(s)"),
            ]
        )

        st.markdown("#### 🔔 À faire aujourd'hui")
        if not (r["retards"] or r["echeances_proches"] or faibles):
            st.success("Rien à signaler : aucune dette en retard, aucune échéance proche, stock suffisant.")
        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f"**🔴 Dettes en retard ({len(r['retards'])})**")
            for d, s in r["retards"][:6]:
                _alerte(
                    d,
                    s,
                    params,
                    config.DANGER_RED,
                    f"{fmt_money(s['montant_retard'])} · {s['jours_retard']} j de retard",
                )
            if not r["retards"]:
                st.caption("Aucune.")
        with k2:
            st.markdown(f"**🟠 À encaisser sous {jours} jours ({len(r['echeances_proches'])})**")
            for d, s in r["echeances_proches"][:6]:
                _alerte(
                    d,
                    s,
                    params,
                    config.WARNING_ORANGE,
                    f"{fmt_money(s['prochain_montant'])} le {fmt_date(s['prochaine_date'])}",
                )
            if not r["echeances_proches"]:
                st.caption("Aucune.")
        with k3:
            st.markdown(f"**📦 Stock faible ({len(faibles)})**")
            for nom, stock in faibles[:6]:
                st.markdown(
                    f"<div class='crm-alert' style='--c:{config.WARNING_ORANGE}'>{escape(nom)} · "
                    f"<b>{stock}</b> restant(s)</div>",
                    unsafe_allow_html=True,
                )
            if not faibles:
                st.caption("Aucun.")

        st.markdown("#### 📈 Activité")
        g1, g2 = st.columns(2)
        with g1.container(border=True):
            st.markdown("**Ventes et argent encaissé (30 jours)**")
            df = get_evolution_ca(30)
            fig = go.Figure()
            fig.add_bar(x=df["Date"], y=df["CA"], name="Ventes", marker_color=config.SECONDARY_BLUE)
            fig.add_scatter(
                x=df["Date"],
                y=df["Encaissé"],
                name="Encaissé",
                mode="lines",
                line=dict(color=config.SUCCESS_GREEN, width=2.5),
            )
            st.plotly_chart(_layout(fig), use_container_width=True)
        with g2.container(border=True):
            st.markdown("**Qui doit le plus ?**")
            if r["top_debiteurs"]:
                dft = pd.DataFrame([(c.nom, m) for c, m in r["top_debiteurs"][:7]], columns=["Client", "Doit"])
                fig = px.bar(
                    dft, x="Doit", y="Client", orientation="h", color_discrete_sequence=[config.WARNING_ORANGE]
                )
                fig.update_yaxes(autorange="reversed", title=None)
                st.plotly_chart(_layout(fig), use_container_width=True)
            else:
                st.info("Personne ne vous doit d'argent 👍")
        g3, g4 = st.columns(2)
        with g3.container(border=True):
            st.markdown(f"**Produits les plus vendus ({periode.lower()})**")
            dfp = get_top_produits(6, debut, fin)
            if dfp.empty:
                st.caption("Aucune vente sur la période.")
            else:
                fig = px.bar(
                    dfp,
                    x="Quantite_vendue",
                    y="Produit",
                    orientation="h",
                    color_discrete_sequence=[config.PRIMARY_BLUE],
                    labels={"Quantite_vendue": "Quantité"},
                )
                fig.update_yaxes(autorange="reversed", title=None)
                st.plotly_chart(_layout(fig), use_container_width=True)
        with g4.container(border=True):
            st.markdown(f"**Moyens de paiement ({periode.lower()})**")
            dfm = get_repartition_paiements(debut, fin)
            if dfm.empty:
                st.caption("Aucun encaissement sur la période.")
            else:
                st.plotly_chart(
                    _layout(px.pie(dfm, names="Mode", values="Montant", hole=0.55)), use_container_width=True
                )


def _alerte(dette, situation, params, couleur, detail):
    msg = D.message_relance(
        params["message_relance"],
        dette.client,
        dette.reste,
        situation["prochaine_date"],
        params["boutique_nom"],
        params["boutique_telephone"],
        fmt_money,
    )
    lien = D.lien_whatsapp(dette.client.telephone, msg)
    wa = f" · <a href='{lien}' target='_blank'>📲 Relancer</a>" if lien else ""
    st.markdown(
        f"<div class='crm-alert' style='--c:{couleur}'><b>{escape(dette.client.nom)}</b> · {detail}{wa}</div>",
        unsafe_allow_html=True,
    )
