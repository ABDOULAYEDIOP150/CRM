"""Tableau de bord : chiffres clés, évolution, marges, produits à recommander, actions du jour, meilleurs clients."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape

import plotly.graph_objects as go
import streamlit as st

import config
from config import fmt_money
from db import alertes as A
from db import dettes as D
from db import tableau as T
from db.models import en_parallele, memoire
from db.utils import get_params
from modules import ui

PERIODES = ["Aujourd'hui", "Cette semaine", "Ce mois", "30 derniers jours", "Cette année"]
COMPARAISON = {"Aujourd'hui": "vs hier", "Cette semaine": "vs sem. préc."}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]  # fmt: skip

# Hauteurs fixes : toutes les cartes d'une même rangée sont alignées
H_RANGEE_1, H_RANGEE_2, H_RANGEE_3 = 330, 270, 300
SANS_BARRE = {"displayModeBar": False}


# ---------------------------------------------------------------- Données (gardées en mémoire)
def _dettes(session):
    session.info["dettes_actives"] = D.dettes_actives(session)  # lues une fois pour les deux calculs
    soldes = defaultdict(float)
    for d in session.info["dettes_actives"]:
        soldes[d.client.nom] += d.reste
    return T.resume_dettes(session), dict(soldes)


def _donnees(periode, seuil):
    debut, fin = config.get_date_range(periode)
    duree = fin - debut
    maintenant = datetime.now()
    minuit = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    r = en_parallele(
        {
            "p": lambda s: T.resume_ventes(s, debut, fin),
            "prec": lambda s: T.resume_ventes(s, debut - duree, debut),
            "dettes": _dettes,
            "stock": lambda s: T.resume_stock(s, seuil),
            "courbe7": lambda s: T.evolution(s, minuit - timedelta(days=6), maintenant),
            "courbe30": lambda s: T.evolution(s, minuit - timedelta(days=29), maintenant),
            "clients": lambda s: (T.top_clients(s, debut, fin, 5), T.clients_recents(s, 5)),
        }
    )
    (dettes, soldes), (top, recents) = r["dettes"], r["clients"]
    return {**r, "dettes": dettes, "soldes": soldes, "top": top, "recents": recents}


# ---------------------------------------------------------------- Graphiques
def _court(v):
    """12 480 000 -> 12,5M ; 41 600 -> 41,6k."""
    for seuil, suffixe in ((1e6, "M"), (1e3, "k")):
        if abs(v) >= seuil:
            return f"{v / seuil:.1f}".replace(".", ",").replace(",0", "") + suffixe
    return f"{v:.0f}"


def _mise_en_page(fig, hauteur):
    fig.update_layout(
        height=hauteur,
        margin=dict(l=4, r=8, t=18, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(size=12, family=f"{config.POLICE}, sans-serif", color="#334155"),
        separators=", ",
        hoverlabel=dict(bgcolor="#fff"),
    )
    return fig


def _courbe(points, hauteur):
    x = [e for e, _ in points]
    y = [v for _, v in points]
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers+text",
            text=[_court(v) for v in y],
            textposition="top center",
            textfont=dict(size=11, color="#0f172a"),
            line=dict(color=ui.BLEU, width=2.5),
            marker=dict(size=7, color=ui.BLEU, line=dict(color="#fff", width=2)),
            fill="tozeroy",
            fillgradient=dict(type="vertical", colorscale=[[0, "rgba(37,99,235,0.02)"], [1, "rgba(37,99,235,0.22)"]]),
            hovertemplate="%{x}<br><b>%{y:,.0f} " + config.DEVISE + "</b><extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_yaxes(tickformat="~s", gridcolor="#eef1f6", zeroline=False, rangemode="tozero", title=None)
    fig.update_xaxes(showgrid=False, title=None, tickfont=dict(size=11, color="#64748b"))
    return _mise_en_page(fig, hauteur)


def _court_libelle(texte):
    """« Ciment & maçonnerie » -> « Ciment » (le nom complet s'affiche au survol)."""
    mot = texte.split()[0] if texte.split() else texte
    return mot if len(mot) <= 10 else mot[:9] + "."


def _barres_categories(marges, hauteur):
    items = [(k, v) for k, v in marges.items() if v > 0][:4]
    total = sum(v for _, v in items) or 1
    fig = go.Figure(
        go.Bar(
            x=[_court_libelle(k) for k, _ in items],
            y=[v for _, v in items],
            text=[f"<b>{v / total:.0%}</b>" for _, v in items],
            textposition="outside",
            textfont=dict(size=12, color="#0f172a"),
            marker=dict(color=ui.PALETTE[: len(items)], cornerradius=6),
            customdata=[k for k, _ in items],
            hovertemplate="%{customdata}<br><b>%{y:,.0f} " + config.DEVISE + "</b> de marge<extra></extra>",
            cliponaxis=False,
            width=0.62,
        )
    )
    fig.update_yaxes(visible=False, rangemode="tozero")
    fig.update_xaxes(tickfont=dict(size=10, color="#475569"), title=None, tickangle=0, automargin=True)
    return _mise_en_page(fig, hauteur)


# ---------------------------------------------------------------- Blocs
def _tete(texte, nom_icone, couleur=ui.BLEU):
    st.markdown(ui.titre_carte(texte, nom_icone, couleur), unsafe_allow_html=True)


def _kpis(p, prec, dettes, stock, periode):
    comparaison = COMPARAISON.get(periode, "vs période préc.")
    du = sum(dettes["tranches"].values())
    en_retard = sum(v for k, v in dettes["tranches"].items() if k != "À jour")
    a_commander = len(stock["ruptures"]) + len(stock["faibles"])
    taux = p["benefice"] / p["ca"] if p["ca"] else 0
    st.markdown(
        ui.grille_kpi(
            [
                ("Chiffre d'affaires", fmt_money(p["ca"]), "panier", ui.BLEU,
                 ui.variation(T.variation(p["ca"], prec["ca"]), comparaison), False),
                ("Marge brute", fmt_money(p["benefice"]), "hausse", ui.VERT,
                 ui.pastille(f"{taux:.1%}".replace(".", ","), ui.VERT if taux >= 0 else ui.ROUGE) if p["ca"] else "", p["benefice"] < 0),
                ("Encaissements", fmt_money(p["encaisse"]), "portefeuille", "#16a34a",
                 ui.variation(T.variation(p["encaisse"], prec["encaisse"]), comparaison), False),
                ("Créances clients", fmt_money(du), "clients", ui.ORANGE,
                 ui.pastille(f"{fmt_money(en_retard)} en retard", ui.ORANGE) if en_retard
                 else ui.pastille("À jour", ui.VERT), False),
                ("Valeur du stock (coût d'achat)", fmt_money(stock["valeur_achat"]), "stock", ui.VIOLET,
                 f"<span class='k-det'>{stock['nb_produits']} produits</span>", False),
                ("À recommander", f"{a_commander} produit{'s' if a_commander > 1 else ''}", "alerte",
                 ui.ROUGE, f"<span class='k-det'>dont {len(stock['ruptures'])} en rupture</span>", a_commander > 0),
            ]
        ),
        unsafe_allow_html=True,
    )  # fmt: skip


def _evolution(d):
    h, s = st.columns([3, 1.1], vertical_alignment="center")
    with h:
        _tete("Évolution des ventes", "graphe")
    choix = s.selectbox("Durée", ["7 jours", "30 jours"], key="dash_courbe", label_visibility="collapsed")
    points = d["courbe7"] if choix == "7 jours" else d["courbe30"]
    if any(v for _, v in points):
        st.plotly_chart(_courbe(points, H_RANGEE_1 - 92), width="stretch", config=SANS_BARRE)
    else:
        st.caption("Aucune vente sur cette durée.")


def _marges(p):
    _tete("Marge par catégorie", "graphe", ui.VIOLET)
    if any(v > 0 for v in p["marge_par_categorie"].values()):
        st.plotly_chart(_barres_categories(p["marge_par_categorie"], H_RANGEE_1 - 82), width="stretch",
                        config=SANS_BARRE)  # fmt: skip
    else:
        st.caption("Aucune vente sur la période.")


def _a_recommander(stock):
    _tete("Produits à recommander", "stock", ui.BLEU)
    liste = sorted(stock["ruptures"], key=lambda p: p.nom) + stock["faibles"]
    if not liste:
        st.success("Aucun produit sous le seuil.")
        return
    seuil_defaut = int(get_params()["seuil_stock"])
    for p in liste[:12]:
        with st.container(key=f"reco_ligne_{p.id}"):
            g, d = st.columns([1.4, 1.1], vertical_alignment="center")
            classe = "zero" if (p.stock or 0) <= 0 else "bas"
            g.markdown(
                f"<span class='reco-nom' title='{escape(p.nom)}'>{escape(p.nom)}</span>"
                f"<span class='reco-sous'>reste <b class='reco-n {classe}'>{p.stock or 0}</b>"
                f" · seuil {p.seuil(seuil_defaut)}</span>",
                unsafe_allow_html=True,
            )
            config.bouton_page(d, "Commander", "Entrees", etat={"produit_cible": p.id}, key=f"cmd_{p.id}",
                               type="primary", width="stretch")  # fmt: skip


def _a_traiter(n):
    _tete("À traiter aujourd'hui", "attention", ui.ORANGE)

    def libelle(nb, un, plusieurs):
        return f"**{nb}** {plusieurs if nb > 1 else un}"

    lignes = [
        ("traiter_retard", n["dette_retard"], "dette en retard de paiement", "dettes en retard de paiement",
         ":material/group:", "Dettes"),
        ("traiter_echeance", n["echeance_aujourdhui"] + n["echeance_proche"], "paiement attendu bientôt",
         "paiements attendus bientôt", ":material/event:", "Dettes"),
        ("traiter_stock", n["rupture"] + n["stock_faible"], "produit sous le seuil", "produits sous le seuil",
         ":material/inventory_2:", "Produits"),
        ("traiter_dormant", n["dormant"], "produit qui ne se vend pas", "produits qui ne se vendent pas",
         ":material/hourglass_empty:", "Alertes"),
    ]  # fmt: skip
    for cle, nb, un, plusieurs, icone, page in lignes:
        config.bouton_page(st, libelle(nb, un, plusieurs), page, key=cle, icon=icone, type="tertiary", width="stretch")


def _top_clients(d, periode):
    h, b = st.columns([3, 1], vertical_alignment="center")
    with h:
        _tete("Top clients", "trophee", ui.ORANGE)
    config.bouton_page(b, "Voir tous", "Clients", key="dash_clients", width="stretch", icon=":material/arrow_forward:")
    if not d["top"]:
        st.caption("Aucun achat de client sur la période.")
        return
    lignes = []
    for nom, total in d["top"]:
        solde = d["soldes"].get(nom, 0)
        lignes.append(
            [
                f"<span class='avatar mini' style='--c:{ui.BLEU}'>{escape(ui._initiales(nom))}</span>{escape(nom)}",
                f"<b>{fmt_money(total)}</b>",
                f"<span class='{'du' if solde else 'ok'}'>{fmt_money(solde)}</span>",
            ]
        )
    colonne = "Achats (" + periode.lower() + ")"
    st.markdown(ui.tableau(["Client", colonne, "Solde dû"], lignes, droite=(1, 2)), unsafe_allow_html=True)


def _bloc(cle, hauteur):
    """Carte blanche à hauteur fixe : les cartes d'une rangée ont la même taille."""
    return st.container(height=hauteur, border=False, key=f"carte_{cle}")


# ---------------------------------------------------------------- Page
def show_dashboard():
    params = get_params()
    seuil = int(params["seuil_stock"])
    aujourd = date.today()
    alertes = A.alertes_memorisees(params)  # déjà calculées pour le menu : 0 requête
    n = A.compter(alertes)

    with st.container(key="barre_dash"):
        c1, c2, c3 = st.columns([3.4, 1.2, 1.7], vertical_alignment="center")
        jour = f"{JOURS[aujourd.weekday()].capitalize()} {aujourd.day} {MOIS[aujourd.month - 1]} {aujourd.year}"
        c1.markdown(ui.titre_page("Tableau de bord", f"{params['boutique_nom']} · {jour}"), unsafe_allow_html=True)
        periode = c2.selectbox("Période", PERIODES, index=PERIODES.index("Ce mois"), key="dash_periode",
                               label_visibility="collapsed")  # fmt: skip
        c3.markdown(ui.utilisateur(n[A.CRITIQUE] + n[A.ATTENTION], params["boutique_nom"]), unsafe_allow_html=True)

    # Gardé en mémoire tant que rien n'est enregistré en base : changer de page puis revenir = instantané
    d = memoire(("tableau_de_bord", periode, aujourd, seuil), lambda: _donnees(periode, seuil))
    p = d["p"]

    a = st.columns([1, 1, 1, 3.3], vertical_alignment="center")
    config.bouton_page(a[0], "Nouvelle vente", "Ventes", type="primary", width="stretch",
                       icon=":material/add_shopping_cart:")  # fmt: skip
    config.bouton_page(a[1], "Nouvel achat", "Entrees", width="stretch", icon=":material/local_shipping:")
    config.bouton_page(a[2], "Encaisser", "Dettes", width="stretch", icon=":material/payments:", key="btn_encaisser")
    a[3].markdown(ui.repartition_paiements(p["par_mode"]), unsafe_allow_html=True)

    _kpis(p, d["prec"], d["dettes"], d["stock"], periode)

    g1, g2, g3 = st.columns([1.5, 1, 1.2])
    with g1, _bloc("evolution", H_RANGEE_1):
        _evolution(d)
    with g2, _bloc("marges", H_RANGEE_1):
        _marges(p)
    with g3, _bloc("recommander", H_RANGEE_1):
        _a_recommander(d["stock"])

    g4, g5 = st.columns([1, 1.45])
    with g4, _bloc("traiter", H_RANGEE_2):
        _a_traiter(n)
    with g5, _bloc("top_clients", H_RANGEE_2):
        _top_clients(d, periode)

    g6, g7, g8 = st.columns(3)
    with g6, _bloc("stock_cat", H_RANGEE_3):
        _tete("Stock par catégorie", "stock", ui.VERT)
        if d["stock"]["par_categorie"]:
            top = dict(list(d["stock"]["par_categorie"].items())[:5])
            st.markdown(ui.barres_progression(top), unsafe_allow_html=True)
        else:
            st.caption("Aucun produit en stock.")
    with g7, _bloc("anciennete", H_RANGEE_3):
        _tete("Ancienneté des dettes", "carte", ui.ROUGE)
        st.markdown(ui.barres_montants(d["dettes"]["tranches"], ui.COULEURS_TRANCHES), unsafe_allow_html=True)
    with g8, _bloc("recents", H_RANGEE_3):
        _tete("Clients récents", "clients")
        if d["recents"]:
            st.markdown(ui.liste_clients(d["recents"][:4], aujourd), unsafe_allow_html=True)
        else:
            st.caption("Aucun client servi pour l'instant.")
