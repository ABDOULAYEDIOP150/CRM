"""Tableau de bord : la journée, les alertes urgentes, puis ventes / dettes / stock / clients en onglets."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from config import fmt_money
from db import alertes as A
from db import dettes as D
from db import tableau as T
from db.models import Produit, get_session
from db.utils import get_evolution_ca, get_params
from modules import ui

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
        font=dict(size=12, family=f"{config.POLICE}, sans-serif"),
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


def _graphe_evolution(points):
    """Courbe du chiffre d'affaires avec zone dégradée ; étiquettes sur les points s'il y en a peu."""
    x = [e for e, _ in points]
    y = [v for _, v in points]
    peu = len(points) <= 12
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers+text" if peu else "lines+markers",
            text=[_court(v) for v in y[:-1]] + [""] if peu else None,  # le dernier a sa bulle
            textposition="top center",
            textfont=dict(size=12, color="#0f172a"),
            line=dict(color=ui.BLEU, width=3, shape="spline", smoothing=0.35),
            marker=dict(size=8 if peu else 5, color=ui.BLEU, line=dict(color="#fff", width=2)),
            fill="tozeroy",
            fillgradient=dict(type="vertical", colorscale=[[0, "rgba(37,99,235,0.02)"], [1, "rgba(37,99,235,0.28)"]]),
            hovertemplate="%{x}<br><b>%{y:,.0f} " + config.DEVISE + "</b><extra></extra>",
            cliponaxis=False,
        )
    )
    if y and y[-1] > 0:  # bulle sur le dernier point
        fig.add_annotation(
            x=x[-1], y=y[-1], text=f"<b>{_court(y[-1])}</b>", showarrow=False, yshift=22,
            bgcolor="#1e3a8a", font=dict(color="#fff", size=12), borderpad=5,
        )  # fmt: skip
    fig.update_yaxes(tickformat="~s", gridcolor="#eef1f6", zeroline=False, rangemode="tozero", title=None)
    fig.update_xaxes(showgrid=False, title=None, tickfont=dict(color="#64748b"))
    _fig(fig, 300)
    fig.update_layout(showlegend=False, separators=", ", hoverlabel=dict(bgcolor="#fff"))
    return fig


def _court(v):
    """12 480 000 -> 12,5M ; 41 600 -> 41,6k."""
    for seuil, suffixe in ((1e6, "M"), (1e3, "k")):
        if abs(v) >= seuil:
            return f"{v / seuil:.1f}".replace(".", ",").replace(",0", "") + suffixe
    return f"{v:.0f}"


def _anneau(valeurs):
    """Anneau seul (la légende est en HTML dessous, plus lisible dans une carte étroite)."""
    fig = go.Figure(
        go.Pie(
            labels=list(valeurs),
            values=list(valeurs.values()),
            hole=0.62,
            sort=False,
            marker=dict(colors=ui.PALETTE[: len(valeurs)], line=dict(color="#fff", width=3)),
            textinfo="none",
            hovertemplate="%{label}<br><b>%{value:,.0f} " + config.DEVISE + "</b> (%{percent})<extra></extra>",
        )
    )
    total = sum(valeurs.values())
    fig.add_annotation(
        text=f"<b>{_court(total)}</b><br><span style='font-size:11px;color:#64748b'>{config.DEVISE}</span>",
        showarrow=False, font=dict(size=20, color="#0f172a"),
    )  # fmt: skip
    _fig(fig, 210)
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0), separators=", ")
    return fig


def _carte(cle):
    """Bloc blanc arrondi (style dans static/styles.css, sélecteur st-key-carte_…)."""
    return st.container(key=f"carte_{cle}")


def show_dashboard():
    params = get_params()
    seuil = int(params["seuil_stock"])
    aujourd = date.today()
    with get_session() as session:
        alertes = A.calculer_alertes(session, params)
        n = A.compter(alertes)

        config.entete(
            "Tableau de bord",
            f"{params['boutique_nom']} · {JOURS[aujourd.weekday()]} {aujourd.day} {MOIS[aujourd.month - 1]} {aujourd.year}",
        )

        # ---------- Actions rapides + période ----------
        b = st.columns([1, 1, 1, 0.6, 1.1], vertical_alignment="center")
        config.bouton_page(b[0], "🛒 Nouvelle vente", "Ventes", type="primary", use_container_width=True)
        config.bouton_page(b[1], "💰 Encaisser", "Dettes", use_container_width=True)
        config.bouton_page(b[2], "📦 Entrée de stock", "Entrees", use_container_width=True)
        periode = b[4].selectbox(
            "Période", PERIODES, index=PERIODES.index("30 derniers jours"), label_visibility="collapsed",
            key="dash_periode", format_func=lambda x: f"📅  {x}",
        )  # fmt: skip
        debut, fin = config.get_date_range(periode)
        duree = fin - debut
        p, prec = T.resume_ventes(session, debut, fin), T.resume_ventes(session, debut - duree, debut)
        dettes = T.resume_dettes(session)
        stock = T.resume_stock(session, seuil)
        du = sum(dettes["tranches"].values())
        en_retard = sum(v for k, v in dettes["tranches"].items() if k != "À jour")

        # ---------- Cartes KPI ----------
        k = st.columns(4)
        cartes = [
            ui.carte_kpi("Chiffre d'affaires", p["ca"], "panier", ui.BLEU, T.variation(p["ca"], prec["ca"])),
            ui.carte_kpi(
                "Bénéfice",
                p["benefice"],
                "hausse",
                ui.VERT,
                T.variation(p["benefice"], prec["benefice"]),
                f"marge {p['benefice'] / p['ca']:.0%}" if p["ca"] else "",
            ),
            ui.carte_kpi(
                "Argent encaissé",
                p["encaisse"],
                "portefeuille",
                ui.VIOLET,
                T.variation(p["encaisse"], prec["encaisse"]),
            ),
            ui.carte_kpi(
                "Dettes à encaisser",
                du,
                "carte",
                ui.ORANGE,
                detail=f"{fmt_money(en_retard)} en retard" if en_retard else "aucun retard",
            ),
        ]
        for col, html in zip(k, cartes, strict=True):
            col.markdown(html, unsafe_allow_html=True)

        j = T.jour(session)
        st.markdown(
            "<div class='bande-jour'><b>Aujourd'hui</b>"
            f"<span>🛒 {fmt_money(j['ca'])} vendus</span><span>💵 {fmt_money(j['encaisse'])} encaissés</span>"
            f"<span>🧾 {j['nb_ventes']} vente(s)</span>"
            f"<span>📈 {fmt_money(j['benefice'])} de bénéfice</span></div>",
            unsafe_allow_html=True,
        )

        # ---------- Évolution · Top produits · Clients récents ----------
        g1, g2, g3 = st.columns([1.7, 1, 1])
        with g1, _carte("evolution"):
            st.markdown(ui.titre_carte(f"Évolution des ventes · {periode.lower()}", "graphe"), unsafe_allow_html=True)
            points = T.evolution(session, debut, fin)
            if any(v for _, v in points):
                st.plotly_chart(_graphe_evolution(points), use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("Aucune vente sur la période.")
        with g2, _carte("top_produits"):
            st.markdown(ui.titre_carte("Top produits", "trophee", ui.ORANGE), unsafe_allow_html=True)
            if p["par_produit"]:
                categories = dict(session.query(Produit.nom, Produit.categorie).all())
                st.markdown(ui.liste_top_produits(p["par_produit"][:5], categories), unsafe_allow_html=True)
            else:
                st.caption("Aucune vente sur la période.")
        with g3, _carte("clients"):
            st.markdown(ui.titre_carte("Clients récents", "clients"), unsafe_allow_html=True)
            recents = T.clients_recents(session, 5)
            if recents:
                st.markdown(ui.liste_clients(recents, aujourd), unsafe_allow_html=True)
                config.bouton_page(st, "Voir tous les clients →", "Clients", key="dash_clients", type="tertiary")
            else:
                st.caption("Aucun client servi pour l'instant.")

        # ---------- Répartition · Stock · Alertes ----------
        g4, g5, g6 = st.columns(3)
        with g4, _carte("repartition"):
            st.markdown(ui.titre_carte("Répartition des ventes", "anneau", ui.VIOLET), unsafe_allow_html=True)
            if p["par_categorie"]:
                st.plotly_chart(_anneau(p["par_categorie"]), use_container_width=True, config={"displayModeBar": False})
                st.markdown(ui.legende(p["par_categorie"]), unsafe_allow_html=True)
            else:
                st.caption("Aucune vente sur la période.")
        with g5, _carte("stock"):
            st.markdown(ui.titre_carte("Stock par catégorie", "stock", ui.VERT), unsafe_allow_html=True)
            if stock["par_categorie"]:
                st.markdown(
                    ui.barres_progression(dict(list(stock["par_categorie"].items())[:6])), unsafe_allow_html=True
                )
                st.caption(f"Part de la valeur du stock · total {fmt_money(stock['valeur_achat'])} au prix d'achat")
            else:
                st.caption("Aucun produit en stock.")
        with g6, _carte("alertes"):
            nb = n[A.CRITIQUE] + n[A.ATTENTION]
            st.markdown(ui.titre_carte(f"Alertes · {nb} à traiter", "cloche", ui.ROUGE), unsafe_allow_html=True)
            urgentes = [a for a in alertes if a.niveau != A.INFO] or alertes
            if urgentes:
                st.markdown(ui.liste_alertes(urgentes[:5]), unsafe_allow_html=True)
                config.bouton_page(st, "Voir et traiter →", "Alertes", key="toutes_alertes", type="tertiary")
            else:
                st.success("Rien à signaler 👍")

        # ---------- Analyse détaillée ----------
        st.markdown("<div class='section-titre'>Analyse détaillée</div>", unsafe_allow_html=True)
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
    config.bouton_page(st, "💳 Gérer les dettes →", "Dettes")


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
