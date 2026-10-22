"""Tableau de bord : la journée, les alertes urgentes, puis ventes / dettes / stock / clients en onglets."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from config import fmt_money
from db import alertes as A
from db import dettes as D
from db import tableau as T
from db.models import get_session
from db.utils import get_evolution_ca, get_params
from modules.alertes import ligne_alerte

PERIODES = ["Cette semaine", "Ce mois", "30 derniers jours", "Cette année"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def _fig(fig, h=300):
    fig.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        height=h,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12),
        font=dict(size=12),
    )
    return fig


def _evol(actuel, precedent, libelle="hier"):
    v = T.variation(actuel, precedent)
    if v is None:
        return f"{libelle} : {fmt_money(precedent)}" if precedent is not None else ""
    fleche = "▲" if v >= 0 else "▼"
    return f"{fleche} {abs(v):.0f} % vs {libelle}"


def _barres(df, x, y, couleur, h=300, fmt_x=True):
    fig = px.bar(df, x=x, y=y, orientation="h", color_discrete_sequence=[couleur], text=x)
    fig.update_traces(texttemplate="%{text:,.0f}" if fmt_x else "%{text}", textposition="outside", cliponaxis=False)
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title=None, showticklabels=False)
    return _fig(fig, h)


def show_dashboard():
    params = get_params()
    seuil = int(params["seuil_stock"])
    aujourd = date.today()
    with get_session() as session:
        alertes = A.calculer_alertes(session, params)
        n = A.compter(alertes)

        # ---------- En-tête + actions rapides ----------
        config.entete(
            "Tableau de bord",
            f"{params['boutique_nom']} · {JOURS[aujourd.weekday()]} {aujourd.day} {MOIS[aujourd.month - 1]} {aujourd.year}",
        )
        b = st.columns(4)
        if b[0].button("🛒 Nouvelle vente", type="primary", use_container_width=True):
            config.aller_a("Ventes")
        if b[1].button("💰 Encaisser une dette", use_container_width=True):
            config.aller_a("Dettes")
        if b[2].button("📦 Ajouter du stock", use_container_width=True):
            config.aller_a("Produits")
        if b[3].button(f"🔔 Alertes ({n[A.CRITIQUE] + n[A.ATTENTION]})", use_container_width=True):
            config.aller_a("Alertes")

        # ---------- Alertes urgentes ----------
        urgentes = [a for a in alertes if a.niveau != A.INFO]
        if urgentes:
            morceaux = [
                f"{n[t]} {A.TYPES[t][1].lower()}"
                for t in ("dette_retard", "echeance_aujourdhui", "echeance_proche", "rupture", "stock_faible")
                if n[t]
            ]
            with st.container(border=True):
                st.markdown(
                    f"#### 🔔 À traiter en priorité  \n<small>{' · '.join(morceaux)}</small>", unsafe_allow_html=True
                )
                for i, a in enumerate(urgentes[:5]):
                    ligne_alerte(a, params, f"dash_{i}")
                if len(urgentes) > 5:
                    if st.button(f"Voir toutes les alertes ({len(urgentes)}) →", key="toutes_alertes"):
                        config.aller_a("Alertes")
        else:
            st.success("✅ Aucune alerte urgente : pas de retard de paiement, pas de rupture de stock.")

        # ---------- Aujourd'hui ----------
        st.markdown("#### 📅 Aujourd'hui")
        j, h = T.jour(session), T.jour(session, aujourd - timedelta(days=1))
        config.kpis(
            [
                ("Ventes du jour", fmt_money(j["ca"]), config.SECONDARY_BLUE, _evol(j["ca"], h["ca"])),
                ("Argent encaissé", fmt_money(j["encaisse"]), config.SUCCESS_GREEN, "comptant + remboursements"),
                (
                    "Bénéfice du jour",
                    fmt_money(j["benefice"]),
                    config.PRIMARY_BLUE,
                    "estimé" if j["marge_complete"] else "partiel : prix d'achat manquants",
                ),
                ("Nombre de ventes", j["nb_ventes"], config.MUTED, f"panier moyen {fmt_money(j['panier_moyen'])}"),
            ]
        )
        if j["par_mode"]:
            st.caption("Caisse du jour : " + "  ·  ".join(f"**{m}** {fmt_money(v)}" for m, v in j["par_mode"].items()))

        # ---------- Période ----------
        st.write("")
        c1, c2 = st.columns([2, 3], vertical_alignment="center")
        c1.markdown("#### 📊 Activité")
        periode = c2.segmented_control("Période", PERIODES, default="Ce mois", label_visibility="collapsed")
        periode = periode or "Ce mois"
        debut, fin = config.get_date_range(periode)
        duree = fin - debut
        p, prec = T.resume_ventes(session, debut, fin), T.resume_ventes(session, debut - duree, debut)
        dettes = T.resume_dettes(session)
        stock = T.resume_stock(session, seuil)
        config.kpis(
            [
                (
                    "Chiffre d'affaires",
                    fmt_money(p["ca"]),
                    config.SECONDARY_BLUE,
                    _evol(p["ca"], prec["ca"], "période préc."),
                ),
                (
                    "Bénéfice",
                    fmt_money(p["benefice"]),
                    config.PRIMARY_BLUE,
                    f"marge {p['benefice'] / p['ca']:.0%}" if p["ca"] else "",
                ),
                (
                    "Encaissé",
                    fmt_money(p["encaisse"]),
                    config.SUCCESS_GREEN,
                    f"dont {fmt_money(p['credit'])} vendus à crédit",
                ),
                (
                    "Dettes à encaisser",
                    fmt_money(sum(dettes["tranches"].values())),
                    config.WARNING_ORANGE,
                    f"{fmt_money(dettes['a_encaisser_semaine'])} prévus sous 7 j",
                ),
                ("Valeur du stock", fmt_money(stock["valeur_achat"]), config.MUTED, "au prix d'achat"),
            ]
        )
        st.write("")

        t1, t2, t3, t4 = st.tabs(["📈 Ventes", "💳 Dettes", "📦 Stock", "👥 Clients"])
        with t1:
            _onglet_ventes(p)
        with t2:
            _onglet_dettes(session, dettes)
        with t3:
            _onglet_stock(stock, n)
        with t4:
            _onglet_clients(session, debut, fin, p)


def _onglet_ventes(p):
    g1, g2 = st.columns(2)
    with g1.container(border=True):
        st.markdown("**Ventes et argent encaissé, jour par jour (30 jours)**")
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
        st.plotly_chart(_fig(fig), use_container_width=True)
    with g2.container(border=True):
        st.markdown("**Ventes par catégorie**")
        if p["par_categorie"]:
            df = pd.DataFrame(list(p["par_categorie"].items()), columns=["Catégorie", "Montant"])
            st.plotly_chart(_barres(df, "Montant", "Catégorie", config.PRIMARY_BLUE), use_container_width=True)
        else:
            st.caption("Aucune vente sur la période.")
    g3, g4 = st.columns(2)
    with g3.container(border=True):
        st.markdown("**Produits qui rapportent le plus**")
        if p["par_produit"]:
            df = pd.DataFrame(p["par_produit"][:8], columns=["Produit", "Quantité", "Montant"])
            st.plotly_chart(_barres(df, "Montant", "Produit", config.SECONDARY_BLUE), use_container_width=True)
        else:
            st.caption("Aucune vente sur la période.")
    with g4.container(border=True):
        st.markdown("**Comment les clients paient**")
        if p["par_mode"]:
            df = pd.DataFrame(list(p["par_mode"].items()), columns=["Moyen", "Montant"])
            st.plotly_chart(_fig(px.pie(df, names="Moyen", values="Montant", hole=0.55)), use_container_width=True)
        else:
            st.caption("Aucun encaissement sur la période.")


def _onglet_dettes(session, d):
    tr = d["tranches"]
    config.kpis(
        [
            ("Total dû par les clients", fmt_money(sum(tr.values())), config.WARNING_ORANGE, ""),
            ("En retard", fmt_money(sum(v for k, v in tr.items() if k != "À jour")), config.DANGER_RED, ""),
            ("Prévu dans les 7 jours", fmt_money(d["a_encaisser_semaine"]), config.SECONDARY_BLUE, ""),
            ("Remboursé ce mois", fmt_money(d["recouvre_mois"]), config.SUCCESS_GREEN, ""),
        ]
    )
    g1, g2 = st.columns(2)
    with g1.container(border=True):
        st.markdown("**Ancienneté des dettes** (plus c'est vieux, plus c'est risqué)")
        df = pd.DataFrame(list(tr.items()), columns=["Tranche", "Montant"])
        fig = px.bar(
            df,
            x="Tranche",
            y="Montant",
            color="Tranche",
            text="Montant",
            color_discrete_sequence=[config.SUCCESS_GREEN, config.WARNING_ORANGE, "#ea580c", config.DANGER_RED],
        )
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None, showticklabels=False)
        st.plotly_chart(_fig(fig), use_container_width=True)
    with g2.container(border=True):
        st.markdown("**Qui doit le plus ?**")
        top = D.resume_creances(session)["top_debiteurs"][:8]
        if top:
            df = pd.DataFrame([(c.nom, m) for c, m in top], columns=["Client", "Doit"])
            st.plotly_chart(_barres(df, "Doit", "Client", config.WARNING_ORANGE), use_container_width=True)
        else:
            st.info("Personne ne vous doit d'argent 👍")
    if st.button("💳 Gérer les dettes →"):
        config.aller_a("Dettes")


def _onglet_stock(s, n):
    config.kpis(
        [
            ("Valeur au prix d'achat", fmt_money(s["valeur_achat"]), config.MUTED, f"{s['nb_produits']} produits"),
            ("Valeur au prix de vente", fmt_money(s["valeur_vente"]), config.SECONDARY_BLUE, "si tout est vendu"),
            ("Ruptures", len(s["ruptures"]), config.DANGER_RED, ", ".join(p.nom for p in s["ruptures"][:3])),
            ("Stock faible", len(s["faibles"]), config.WARNING_ORANGE, ", ".join(p.nom for p in s["faibles"][:3])),
        ]
    )
    g1, g2 = st.columns(2)
    with g1.container(border=True):
        st.markdown("**🛒 À commander**")
        a_commander = s["ruptures"] + s["faibles"]
        if a_commander:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Produit": p.nom,
                            "Catégorie": p.categorie or "Divers",
                            "Reste": f"{p.stock} {p.unite or 'pièce'}",
                        }
                        for p in a_commander
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.success("Rien à commander.")
    with g2.container(border=True):
        st.markdown("**Où est votre argent immobilisé ?** (stock par catégorie)")
        if s["par_categorie"]:
            df = pd.DataFrame(list(s["par_categorie"].items()), columns=["Catégorie", "Valeur"])
            st.plotly_chart(_barres(df, "Valeur", "Catégorie", config.MUTED), use_container_width=True)
    if n["dormant"]:
        st.caption(f"💤 {n['dormant']} produit(s) ne se vendent pas : voir la page Alertes.")


def _onglet_clients(session, debut, fin, p):
    config.kpis(
        [
            ("Clients servis", p["clients"], config.SECONDARY_BLUE, "sur la période"),
            ("Nouveaux clients", T.nouveaux_clients(session, debut, fin), config.SUCCESS_GREEN, "sur la période"),
            ("Panier moyen", fmt_money(p["panier_moyen"]), config.MUTED, ""),
        ]
    )
    with st.container(border=True):
        st.markdown("**Meilleurs clients de la période**")
        top = T.top_clients(session, debut, fin, 8)
        if top:
            df = pd.DataFrame(top, columns=["Client", "Achats"])
            st.plotly_chart(_barres(df, "Achats", "Client", config.SUCCESS_GREEN), use_container_width=True)
        else:
            st.caption("Aucun achat de client enregistré sur la période.")
