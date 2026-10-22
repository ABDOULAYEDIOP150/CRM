import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from config import fmt_money, fmt_date, stat_card
from db.models import get_session, Produit
from db.utils import get_stats_periode, get_top_produits, get_evolution_ca, get_params, get_repartition_paiements
from db import dettes as D


def show_dashboard():
    params = get_params()
    seuil_stock = int(params["seuil_stock"])
    jours_alerte = int(params["jours_alerte_echeance"])

    periode = st.radio("Période", ["Aujourd'hui", "Cette semaine", "Ce mois", "Cette année", "30 derniers jours"],
                       index=2, horizontal=True, label_visibility="collapsed")
    debut, fin = config.get_date_range(periode)
    stats = get_stats_periode(debut, fin)

    with get_session() as session:
        r = D.resume_creances(session, jours_alerte=jours_alerte)
        stock_faible = session.query(Produit).filter(Produit.stock <= seuil_stock).order_by(Produit.stock).all()
        stock_faible = [(p.nom, p.stock) for p in stock_faible]

        # ---------- KPI ----------
        c = st.columns(5)
        c[0].markdown(stat_card("Chiffre d'affaires", fmt_money(stats["ca_total"]),
                                sous_titre=f"{stats['nb_ventes']} vente(s)"), unsafe_allow_html=True)
        c[1].markdown(stat_card("Encaissé", fmt_money(stats["encaisse"]), config.SUCCESS_GREEN,
                                "argent réellement reçu"), unsafe_allow_html=True)
        c[2].markdown(stat_card("Marge estimée", fmt_money(stats["marge"]), config.SECONDARY_BLUE,
                                "si prix d'achat renseignés"), unsafe_allow_html=True)
        c[3].markdown(stat_card("Dettes à recevoir", fmt_money(r["total_du"]), config.WARNING_ORANGE,
                                f"{r['nb_debiteurs']} client(s)"), unsafe_allow_html=True)
        c[4].markdown(stat_card("Dont en retard", fmt_money(r["montant_retard"]), config.DANGER_RED,
                                f"{len(r['retards'])} dette(s)"), unsafe_allow_html=True)

        # ---------- Alertes ----------
        nb_alertes = len(r["retards"]) + len(r["echeances_proches"]) + len(stock_faible)
        st.markdown(f"### 🔔 Alertes ({nb_alertes})")
        if nb_alertes == 0:
            st.success("Aucune alerte : pas de retard, pas d'échéance proche, stock suffisant.")
        a1, a2, a3 = st.columns(3)
        with a1:
            if r["retards"]:
                st.markdown("**🔴 Dettes en retard**")
                for d, s in r["retards"][:8]:
                    _alerte(d, s, params, "#fee2e2", "#991b1b",
                            f"{fmt_money(s['montant_retard'])} en retard depuis {s['jours_retard']} j")
        with a2:
            if r["echeances_proches"]:
                st.markdown(f"**🟠 Échéances dans les {jours_alerte} jours**")
                for d, s in r["echeances_proches"][:8]:
                    _alerte(d, s, params, "#fef3c7", "#92400e",
                            f"{fmt_money(s['prochain_montant'])} le {fmt_date(s['prochaine_date'])}")
        with a3:
            if stock_faible:
                st.markdown("**📦 Stock faible**")
                for nom, stock in stock_faible[:10]:
                    st.markdown(f"<div style='background:#fef9c3;color:#854d0e;padding:6px 10px;border-radius:6px;"
                                f"margin-bottom:4px'>{nom} — <b>{stock}</b> restant(s)</div>",
                                unsafe_allow_html=True)
        if len(r["retards"]) > 8 or len(r["echeances_proches"]) > 8:
            st.caption("Liste complète dans 💳 Dettes.")

        # ---------- Graphiques ----------
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Ventes vs encaissements (30 jours)**")
            df = get_evolution_ca(30)
            fig = go.Figure()
            fig.add_bar(x=df["Date"], y=df["CA"], name="Ventes", marker_color=config.SECONDARY_BLUE)
            fig.add_scatter(x=df["Date"], y=df["Encaissé"], name="Encaissé", mode="lines+markers",
                            line=dict(color=config.SUCCESS_GREEN, width=2))
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300,
                              legend=dict(orientation="h", y=1.1), yaxis_title="FCFA")
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.markdown("**Top débiteurs**")
            if r["top_debiteurs"]:
                dft = pd.DataFrame([(c.nom, m) for c, m in r["top_debiteurs"][:8]], columns=["Client", "Reste dû"])
                fig = px.bar(dft, x="Reste dû", y="Client", orientation="h", color_discrete_sequence=[config.WARNING_ORANGE])
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune dette en cours 👍")

        g3, g4 = st.columns(2)
        with g3:
            st.markdown("**Top produits (période)**")
            dfp = get_top_produits(5, debut, fin)
            if not dfp.empty:
                fig = px.bar(dfp, x="Produit", y="Quantite_vendue", color_discrete_sequence=[config.PRIMARY_BLUE])
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Aucune vente sur la période.")
        with g4:
            st.markdown("**Encaissements par moyen de paiement (période)**")
            dfm = get_repartition_paiements(debut, fin)
            if not dfm.empty:
                fig = px.pie(dfm, names="Mode", values="Montant", hole=0.5)
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Aucun encaissement sur la période.")


def _alerte(dette, situation, params, fond, texte, detail):
    msg = D.message_relance(params["message_relance"], dette.client, dette.reste, situation["prochaine_date"],
                            params["boutique_nom"], params["boutique_telephone"], fmt_money)
    lien = D.lien_whatsapp(dette.client.telephone, msg)
    wa = f" · <a href='{lien}' target='_blank'>📲 Relancer</a>" if lien else ""
    st.markdown(f"<div style='background:{fond};color:{texte};padding:6px 10px;border-radius:6px;margin-bottom:4px'>"
                f"<b>{dette.client.nom}</b> — {detail}{wa}</div>", unsafe_allow_html=True)
