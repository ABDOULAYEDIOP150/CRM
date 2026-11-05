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
from db.models import Produit, en_parallele, memoire
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


def _dettes_et_debiteurs(session):
    session.info["dettes_actives"] = D.dettes_actives(session)  # lues une fois pour les deux calculs
    return T.resume_dettes(session), [(c.nom, m) for c, m in D.resume_creances(session)["top_debiteurs"][:8]]


def _stock_et_categories(session, seuil):
    return T.resume_stock(session, seuil), dict(session.query(Produit.nom, Produit.categorie).all())


def _donnees(periode, seuil):
    """Tous les chiffres du tableau de bord. Les blocs indépendants sont lus en parallèle."""
    debut, fin = config.get_date_range(periode)
    duree = fin - debut
    r = en_parallele(
        {
            "p": lambda s: T.resume_ventes(s, debut, fin),
            "prec": lambda s: T.resume_ventes(s, debut - duree, debut),
            "jour": T.jour,
            "dettes": _dettes_et_debiteurs,
            "stock": lambda s: _stock_et_categories(s, seuil),
            "courbe": lambda s: (T.evolution(s, debut, fin), T.clients_recents(s, 5)),
            "clients": lambda s: (T.nouveaux_clients(s, debut, fin), T.top_clients(s, debut, fin, 8)),
            "evolution_30j": lambda s: get_evolution_ca(30),
        }
    )
    (dettes, top_debiteurs), (stock, categories) = r["dettes"], r["stock"]
    (points, recents), (nouveaux, top_clients) = r["courbe"], r["clients"]
    return {
        "p": r["p"], "prec": r["prec"], "jour": r["jour"], "dettes": dettes, "top_debiteurs": top_debiteurs,
        "stock": stock, "categories": categories, "points": points, "recents": recents, "nouveaux": nouveaux,
        "top_clients": top_clients, "evolution_30j": r["evolution_30j"],
    }  # fmt: skip


def show_dashboard():
    params = get_params()
    seuil = int(params["seuil_stock"])
    aujourd = date.today()
    alertes = A.alertes_memorisees(params)  # déjà calculées pour le menu : 0 requête
    n = A.compter(alertes)

    config.entete(
        "Tableau de bord",
        f"{JOURS[aujourd.weekday()].capitalize()} {aujourd.day} {MOIS[aujourd.month - 1]} {aujourd.year}",
    )

    # ---------- Actions rapides + période ----------
    b = st.columns([1, 1, 1, 0.6, 1.1], vertical_alignment="center")
    config.bouton_page(
        b[0], "Nouvelle vente", "Ventes", type="primary", width="stretch", icon=":material/add_shopping_cart:"
    )
    config.bouton_page(b[1], "Encaisser", "Dettes", width="stretch", icon=":material/payments:")
    config.bouton_page(b[2], "Entrée de stock", "Entrees", width="stretch", icon=":material/move_to_inbox:")
    periode = b[4].selectbox(
        "Période", PERIODES, index=PERIODES.index("30 derniers jours"), label_visibility="collapsed",
        key="dash_periode", format_func=lambda x: f"{x}",
    )  # fmt: skip
    # Gardé en mémoire tant que rien n'est enregistré en base : changer de page puis revenir = instantané
    d = memoire(("tableau_de_bord", periode, aujourd, seuil), lambda: _donnees(periode, seuil))
    p, prec, dettes, stock = d["p"], d["prec"], d["dettes"], d["stock"]
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

    j = d["jour"]
    st.markdown(
        "<div class='bande-jour'><b>Aujourd'hui</b>"
        f"<span>{fmt_money(j['ca'])} vendus</span><span>{fmt_money(j['encaisse'])} encaissés</span>"
        f"<span>{j['nb_ventes']} vente(s)</span>"
        f"<span>{fmt_money(j['benefice'])} de bénéfice</span></div>",
        unsafe_allow_html=True,
    )

    # ---------- Évolution · Top produits · Clients récents ----------
    g1, g2, g3 = st.columns([1.7, 1, 1])
    with g1, _carte("evolution"):
        st.markdown(ui.titre_carte(f"Évolution des ventes · {periode.lower()}", "graphe"), unsafe_allow_html=True)
        points = d["points"]
        if any(v for _, v in points):
            st.plotly_chart(_graphe_evolution(points), width="stretch", config={"displayModeBar": False})
        else:
            st.caption("Aucune vente sur la période.")
    with g2, _carte("top_produits"):
        st.markdown(ui.titre_carte("Top produits", "trophee", ui.ORANGE), unsafe_allow_html=True)
        if p["par_produit"]:
            categories = d["categories"]
            st.markdown(ui.liste_top_produits(p["par_produit"][:5], categories), unsafe_allow_html=True)
        else:
            st.caption("Aucune vente sur la période.")
    with g3, _carte("clients"):
        st.markdown(ui.titre_carte("Clients récents", "clients"), unsafe_allow_html=True)
        recents = d["recents"]
        if recents:
            st.markdown(ui.liste_clients(recents, aujourd), unsafe_allow_html=True)
            config.bouton_page(st, "Voir tous les clients", "Clients", key="dash_clients", type="tertiary")
        else:
            st.caption("Aucun client servi pour l'instant.")

    # ---------- Répartition · Stock · Alertes ----------
    g4, g5, g6 = st.columns(3)
    with g4, _carte("repartition"):
        st.markdown(ui.titre_carte("Répartition des ventes", "anneau", ui.VIOLET), unsafe_allow_html=True)
        if p["par_categorie"]:
            st.plotly_chart(_anneau(p["par_categorie"]), width="stretch", config={"displayModeBar": False})
            st.markdown(ui.legende(p["par_categorie"]), unsafe_allow_html=True)
        else:
            st.caption("Aucune vente sur la période.")
    with g5, _carte("stock"):
        st.markdown(ui.titre_carte("Stock par catégorie", "stock", ui.VERT), unsafe_allow_html=True)
        if stock["par_categorie"]:
            st.markdown(ui.barres_progression(dict(list(stock["par_categorie"].items())[:6])), unsafe_allow_html=True)
            st.caption(f"Valeur totale au prix d'achat : {fmt_money(stock['valeur_achat'])}")
        else:
            st.caption("Aucun produit en stock.")
    with g6, _carte("alertes"):
        nb = n[A.CRITIQUE] + n[A.ATTENTION]
        st.markdown(ui.titre_carte(f"Alertes · {nb} à traiter", "cloche", ui.ROUGE), unsafe_allow_html=True)
        urgentes = [a for a in alertes if a.niveau != A.INFO] or alertes
        if urgentes:
            st.markdown(ui.liste_alertes(urgentes[:5]), unsafe_allow_html=True)
            config.bouton_page(st, "Voir toutes les alertes", "Alertes", key="toutes_alertes", type="tertiary")
        else:
            st.success("Rien à signaler ")

    # ---------- Analyse détaillée ----------
    st.markdown("<div class='section-titre'>Analyse détaillée</div>", unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["Ventes", "Dettes", "Stock", "Clients"])
    with t1:
        _onglet_ventes(p, d["evolution_30j"])
    with t2:
        _onglet_dettes(dettes, d["top_debiteurs"])
    with t3:
        _onglet_stock(stock, n)
    with t4:
        _onglet_clients(p, d["nouveaux"], d["top_clients"])


def _onglet_ventes(p, df_30j):
    g1, g2 = st.columns(2)
    with config.carte(g1):
        st.markdown("**Ventes et encaissements, 30 jours**")
        df = df_30j
        fig = go.Figure()
        fig.add_bar(x=df["Date"], y=df["CA"], name="Ventes", marker_color=config.SECONDARY_BLUE)
        fig.add_scatter(
            x=df["Date"],
            y=df["Encaissé"],
            name="Encaissé",
            mode="lines",
            line=dict(color=config.SUCCESS_GREEN, width=2.5),
        )
        st.plotly_chart(_fig(fig), width="stretch")
    with config.carte(g2):
        st.markdown("**Ventes par catégorie**")
        if p["par_categorie"]:
            df = pd.DataFrame(list(p["par_categorie"].items()), columns=["Catégorie", "Montant"])
            st.plotly_chart(_barres(df, "Montant", "Catégorie", config.PRIMARY_BLUE), width="stretch")
        else:
            st.caption("Aucune vente sur la période.")
    g3, g4 = st.columns(2)
    with config.carte(g3):
        st.markdown("**Produits les plus vendus**")
        if p["par_produit"]:
            df = pd.DataFrame(p["par_produit"][:8], columns=["Produit", "Quantité", "Montant"])
            st.plotly_chart(_barres(df, "Montant", "Produit", config.SECONDARY_BLUE), width="stretch")
        else:
            st.caption("Aucune vente sur la période.")
    with config.carte(g4):
        st.markdown("**Moyens de paiement**")
        if p["par_mode"]:
            df = pd.DataFrame(list(p["par_mode"].items()), columns=["Moyen", "Montant"])
            st.plotly_chart(_fig(px.pie(df, names="Moyen", values="Montant", hole=0.55)), width="stretch")
        else:
            st.caption("Aucun encaissement sur la période.")


def _onglet_dettes(d, top):
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
    with config.carte(g1):
        st.markdown("**Ancienneté des dettes**")
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
        st.plotly_chart(_fig(fig), width="stretch")
    with config.carte(g2):
        st.markdown("**Qui doit le plus ?**")
        if top:
            df = pd.DataFrame(top, columns=["Client", "Doit"])
            st.plotly_chart(_barres(df, "Doit", "Client", config.WARNING_ORANGE), width="stretch")
        else:
            st.info("Aucune dette en cours.")
    config.bouton_page(st, "Gérer les dettes", "Dettes")


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
    with config.carte(g1):
        st.markdown("**À commander**")
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
                width="stretch",
            )
        else:
            st.success("Rien à commander.")
    with config.carte(g2):
        st.markdown("**Valeur du stock par catégorie**")
        if s["par_categorie"]:
            df = pd.DataFrame(list(s["par_categorie"].items()), columns=["Catégorie", "Valeur"])
            st.plotly_chart(_barres(df, "Valeur", "Catégorie", config.MUTED), width="stretch")


def _onglet_clients(p, nouveaux, top):
    config.kpis(
        [
            ("Clients servis", p["clients"], config.SECONDARY_BLUE, "sur la période"),
            ("Nouveaux clients", nouveaux, config.SUCCESS_GREEN, "sur la période"),
            ("Panier moyen", fmt_money(p["panier_moyen"]), config.MUTED, ""),
        ]
    )
    with config.carte():
        st.markdown("**Meilleurs clients**")
        if top:
            df = pd.DataFrame(top, columns=["Client", "Achats"])
            st.plotly_chart(_barres(df, "Achats", "Client", config.SUCCESS_GREEN), width="stretch")
        else:
            st.caption("Aucun achat de client enregistré sur la période.")
