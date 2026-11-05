"""Stock : ce qu'il y a en magasin, la valeur, la marge, le détail des arrivages, l'inventaire et le journal."""

import pandas as pd
import streamlit as st

import config
from config import fmt_date, fmt_money
from db.models import MouvementStock, Produit, get_session
from db.stock import fixer_stock, marge
from db.utils import get_param
from modules.tableaux import styliser

TYPES_MVT = ["Vente", "Réception", "Import", "Inventaire", "Correction", "Création"]


def _etat(p, seuil):
    if (p.stock or 0) <= 0:
        return "Rupture" if p.lots else "Jamais acheté"
    return "Faible" if p.stock <= p.seuil(seuil) else "OK"


def show_produits():
    seuil = int(get_param("seuil_stock"))
    with get_session() as session:
        config.entete("Stock", "Quantités, valeur et marges")
        produits = session.query(Produit).order_by(Produit.categorie, Produit.nom).all()
        ruptures = [p for p in produits if (p.stock or 0) <= 0 and p.lots]  # jamais acheté : pas une rupture
        faibles = [p for p in produits if 0 < (p.stock or 0) <= p.seuil(seuil)]
        valeur_achat = sum((p.prix_achat or 0) * max(p.stock or 0, 0) for p in produits)
        valeur_vente = sum((p.prix or 0) * max(p.stock or 0, 0) for p in produits)
        config.kpis(
            [
                ("Valeur du stock", fmt_money(valeur_achat), config.SECONDARY_BLUE, "au prix d'achat"),
                (
                    "Si tout est vendu",
                    fmt_money(valeur_vente),
                    config.SUCCESS_GREEN,
                    f"bénéfice attendu {fmt_money(valeur_vente - valeur_achat)}",
                ),
                (
                    "Ruptures",
                    len(ruptures),
                    config.DANGER_RED if ruptures else config.MUTED,
                    ", ".join(p.nom for p in ruptures[:2]) + ("…" if len(ruptures) > 2 else ""),
                ),
                (
                    "Stock faible",
                    len(faibles),
                    config.WARNING_ORANGE if faibles else config.MUTED,
                    ", ".join(p.nom for p in faibles[:3]),
                ),
            ]
        )
        st.write("")
        a, b, c = st.columns([1.4, 1.4, 3], vertical_alignment="bottom")
        config.bouton_page(a, "Entrée de stock", "Entrees", type="primary", width="stretch")
        config.bouton_page(b, "Base produits", "Catalogue", width="stretch")
        filtre = c.text_input("Filtrer", placeholder="Code, nom ou catégorie…", label_visibility="collapsed")
        if filtre:
            f = filtre.lower()
            produits = [p for p in produits if f in f"{p.reference} {p.nom} {p.categorie}".lower()]
        t1, t2, t3 = st.tabs(["État du stock", "Inventaire (comptage)", "Mouvements"])
        with t1:
            _etat_stock(session, produits, seuil)
        with t2:
            _inventaire(session, produits)
        with t3:
            _mouvements(session, produits)


def _etat_stock(session, produits, seuil):
    if not produits:
        st.info("Aucun produit.")
        return
    lignes = []
    for p in produits:
        gain, taux = marge(p.prix_achat or 0, p.prix or 0)
        lignes.append(
            {
                "Code": p.reference,
                "Produit": p.nom,
                "Catégorie": p.categorie or "Divers",
                "Stock": f"{p.stock or 0} {p.unite or ''}".strip(),
                "Prix d'achat moyen": p.prix_achat or 0,
                "Prix de vente": p.prix or 0,
                "Marge": f"{taux:.0%}" if p.prix else "",
                "Valeur (achat)": (p.prix_achat or 0) * max(p.stock or 0, 0),
                "État": _etat(p, seuil),
            }
        )
    event = st.dataframe(
        styliser(pd.DataFrame(lignes)),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="table_stock",
        column_config={
            k: st.column_config.NumberColumn(format="localized")
            for k in ["Prix d'achat moyen", "Prix de vente", "Valeur (achat)"]
        },
    )
    if not event.selection.rows:
        return
    p = produits[event.selection.rows[0]]
    unite = p.unite or "pièce"
    st.divider()
    st.markdown(f"### {p.reference} · {p.nom}")
    g, d = st.columns([3, 2], gap="large")
    with g:
        st.markdown("**Arrivages**")
        if p.lots:
            st.dataframe(
                styliser(
                    pd.DataFrame(
                        [
                            {
                                "Date": fmt_date(l.date),
                                "Acheté": l.quantite,
                                "Reste": l.restant,
                                "Prix d'achat": l.prix_achat,
                                "Prix de vente": l.prix_vente,
                                "Fournisseur": l.fournisseur or "",
                                "Note": l.note,
                            }
                            for l in reversed(p.lots)
                        ]
                    )
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    k: st.column_config.NumberColumn(format="localized") for k in ["Prix d'achat", "Prix de vente"]
                },
            )
        else:
            st.caption("Aucun arrivage.")
    with d, config.carte():
        st.markdown("**Prix de vente**")
        nouveau = st.number_input(
            f"Prix de vente d'un(e) {unite}", min_value=0, step=50, value=int(p.prix or 0), key=f"pv_{p.id}"
        )
        gain, taux = marge(p.prix_achat or 0, nouveau)
        (st.error if nouveau < (p.prix_achat or 0) else st.caption)(
            f"Marge : {fmt_money(gain)} par {unite} ({taux:.0%}) sur un prix d'achat moyen de {fmt_money(p.prix_achat)}"
        )
        if nouveau != int(p.prix or 0) and st.button("Appliquer ce prix", type="primary"):
            p.prix = nouveau
            session.commit()
            config.flash(f"Nouveau prix de {p.nom} : {fmt_money(nouveau)}.")
            st.rerun()


def _inventaire(session, produits):
    if not produits:
        return
    df = pd.DataFrame(
        [
            {
                "id": p.id,
                "Code": p.reference,
                "Produit": p.nom,
                "Unité": p.unite or "pièce",
                "Théorique": int(p.stock or 0),
                "Compté": int(p.stock or 0),
            }
            for p in produits
        ]
    )
    edite = st.data_editor(
        styliser(df),
        hide_index=True,
        width="stretch",
        key="editeur_inventaire",
        disabled=["Code", "Produit", "Unité", "Théorique"],
        column_config={"id": None, "Compté": st.column_config.NumberColumn(min_value=0, step=1)},
    )
    ecarts = edite[edite["Compté"] != edite["Théorique"]]
    if ecarts.empty:
        return
    perte = sum(
        (r["Théorique"] - r["Compté"]) * (session.get(Produit, int(r["id"])).prix_achat or 0)
        for _, r in ecarts.iterrows()
    )
    st.warning(f"{len(ecarts)} écart(s) · valeur {'perdue' if perte > 0 else 'retrouvée'} : {fmt_money(abs(perte))}")
    if st.button("Valider l'inventaire", type="primary"):
        for _, r in ecarts.iterrows():
            fixer_stock(
                session,
                session.get(Produit, int(r["id"])),
                int(r["Compté"]),
                "Inventaire",
                f"Inventaire : {r['Théorique']} attendu(s), {r['Compté']} compté(s)",
            )
        session.commit()
        st.session_state.pop("editeur_inventaire", None)
        config.flash("Inventaire enregistré.")
        st.rerun()


def _mouvements(session, produits):
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
