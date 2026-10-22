"""📥 Entrée de stock : je choisis un produit du catalogue (par son code ou son nom), je dis combien j'en ai
acheté, à quel prix, et à combien je vais le revendre. L'application calcule la marge et met le stock à jour."""

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

import config
from config import fmt_date, fmt_money
from db.models import LotStock, Produit, get_session
from db.stock import ErreurStock, entree_stock, marge
from db.utils import get_param
from modules.catalogue import dialog_produit

PAR_UNITE = "Prix unitaire"
TOTAL = "Total payé"


def _fournisseurs(session):
    return sorted({l.fournisseur for l in session.query(LotStock) if l.fournisseur})


def show_entrees():
    with get_session() as session:
        config.entete(
            "Entrée de stock",
            "Choisissez le produit, indiquez la quantité achetée, le prix d'achat et le prix de vente.",
        )
        produits = session.query(Produit).order_by(Produit.nom).all()
        if not produits:
            st.info("Le catalogue est vide : ajoutez d'abord vos produits.")
            if st.button("➕ Nouveau produit", type="primary"):
                dialog_produit()
            return
        gauche, droite = st.columns([3, 2], gap="large")
        with gauche:
            _formulaire(session, produits)
        with droite:
            _fiche_produit(session)
        st.divider()
        _historique(session)


def _formulaire(session, produits):
    par_id = {p.id: p for p in produits}
    cible = st.session_state.pop("produit_cible", None)
    if cible in par_id:
        st.session_state["entree_produit"] = cible
    with st.container(border=True):
        st.markdown("##### ① Produit")
        a, b = st.columns([4, 1], vertical_alignment="bottom")
        pid = a.selectbox(
            "Produit",
            list(par_id),
            index=None,
            key="entree_produit",
            placeholder="🔎  Tapez le code ou le nom (ex. « SAB » ou « sable »)",
            format_func=lambda i: f"{par_id[i].reference} · {par_id[i].nom}  ({par_id[i].unite or 'pièce'})",
            label_visibility="collapsed",
        )
        if b.button("➕", use_container_width=True, help="Nouveau produit (absent du catalogue)"):
            dialog_produit()
        st.session_state["entree_fiche"] = pid
        if pid is None:
            st.caption("Choisissez un produit pour continuer.")
            return
        p = par_id[pid]
        unite = p.unite or "pièce"

        st.markdown("##### ② Achat")
        c1, c2 = st.columns(2)
        quantite = c1.number_input(f"Quantité achetée ({unite})", min_value=1, step=1, value=1, key="entree_qte")
        mode_prix = (
            c2.segmented_control("Je connais…", [PAR_UNITE, TOTAL], default=PAR_UNITE, key="entree_mode") or PAR_UNITE
        )
        dernier = p.lots[-1].prix_achat if p.lots else (p.prix_achat or 0)
        if mode_prix == PAR_UNITE:
            pa = st.number_input(
                f"Prix d'achat d'un(e) {unite} (FCFA)", min_value=0, step=50, value=int(dernier), key=f"entree_pa_{pid}"
            )
        else:
            total = st.number_input(
                "Montant total payé au fournisseur (FCFA)",
                min_value=0,
                step=500,
                value=int(dernier * quantite),
                key=f"entree_total_{pid}",
            )
            pa = round(total / quantite) if quantite else 0
            st.caption(f"Soit **{fmt_money(pa)}** par {unite}.")
        f1, f2 = st.columns(2)
        fournisseurs = _fournisseurs(session)
        fournisseur = f1.selectbox(
            "Fournisseur (facultatif)",
            fournisseurs,
            index=None,
            accept_new_options=True,
            placeholder="Choisir ou taper un nom",
            key="entree_fournisseur",
        )
        jour = f2.date_input("Date de l'achat", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")

        st.markdown("##### ③ Prix de vente")
        taux = float(get_param("marge_defaut") or 20)
        propose = int(round(pa * (1 + taux / 100), -1)) if pa else int(p.prix or 0)
        defaut = int(p.prix) if p.prix and p.prix >= pa else propose
        v1, v2 = st.columns([2, 3], vertical_alignment="bottom")
        pv = v1.number_input(
            f"Je vends un(e) {unite} à (FCFA)", min_value=0, step=50, value=defaut, key=f"entree_pv_{pid}_{pa}"
        )
        v2.caption(
            f"Prix actuel : {fmt_money(p.prix) if p.prix else '—'} · avec {taux:.0f} % de marge : {fmt_money(propose)}"
        )
        gain, taux_reel = marge(pa, pv)
        if pv and pv < pa:
            st.error(f"⚠️ Vous vendriez à perte : {fmt_money(-gain)} perdus par {unite}.")
        elif pv:
            st.success(
                f"Bénéfice : **{fmt_money(gain)} par {unite}** ({taux_reel:.0%}) · "
                f"**{fmt_money(gain * quantite)}** si tout l'arrivage est vendu."
            )

        recap = f"{quantite} {unite}(s) de {p.nom} à {fmt_money(pa)} = {fmt_money(pa * quantite)}"
        if st.button(f"✅ Enregistrer l'entrée : {recap}", type="primary", use_container_width=True, disabled=not pv):
            try:
                quand = datetime.combine(jour, datetime.now().time()) if jour != date.today() else None
                entree_stock(session, p, quantite, pa, pv, fournisseur or "", date=quand)
                session.commit()
            except ErreurStock as e:
                session.rollback()
                st.error(str(e))
                return
            for k in [k for k in st.session_state if str(k).startswith("entree_") and k != "entree_produit"]:
                st.session_state.pop(k, None)
            config.flash(f"Entrée enregistrée : +{quantite} {unite}(s) de {p.nom}. Stock : {p.stock}.")
            st.rerun()


def _fiche_produit(session):
    pid = st.session_state.get("entree_fiche")
    p = session.get(Produit, pid) if pid else None
    with st.container(border=True):
        if p is None:
            st.markdown("##### Comment ça marche ?")
            st.markdown(
                "1. Le **catalogue** contient vos produits avec un code (ex. SAB-001 = Sable).\n"
                "2. À chaque achat, faites une **entrée de stock** : quantité, prix d'achat, prix de vente.\n"
                "3. Chaque arrivage garde **son propre prix d'achat** : si le prix du fournisseur change, "
                "le bénéfice reste exact (les plus anciens sont vendus en premier)."
            )
            return
        unite = p.unite or "pièce"
        st.markdown(f"##### {p.reference} · {p.nom}")
        st.markdown(
            f"📦 En stock : **{p.stock or 0} {unite}**  \n"
            f"💰 Prix d'achat moyen : **{fmt_money(p.prix_achat)}**  \n"
            f"🏷️ Prix de vente actuel : **{fmt_money(p.prix) if p.prix else '—'}**"
        )
        if p.lots:
            st.markdown("**Derniers achats**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Date": l.date.strftime("%d/%m/%Y"),
                            "Qté": l.quantite,
                            "Reste": l.restant,
                            "Prix achat": l.prix_achat,
                            "Prix vente": l.prix_vente,
                            "Fournisseur": l.fournisseur or "—",
                        }
                        for l in reversed(p.lots[-6:])
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={
                    k: st.column_config.NumberColumn(format="localized") for k in ["Prix achat", "Prix vente"]
                },
            )
            prix = [l.prix_achat for l in p.lots]
            if len(prix) > 1 and prix[-1] != prix[-2]:
                sens = "augmenté" if prix[-1] > prix[-2] else "baissé"
                st.caption(f"📈 Le prix d'achat a {sens} : {fmt_money(prix[-2])} → {fmt_money(prix[-1])}.")
        else:
            st.caption("Aucun achat enregistré pour ce produit.")


def _historique(session):
    st.markdown("#### 📜 Historique des entrées de stock")
    a, b, c = st.columns([2, 2, 3])
    periode = a.date_input(
        "Période", value=(date.today() - timedelta(days=30), date.today()), format="DD/MM/YYYY", key="hist_entrees"
    )
    fournisseur = b.selectbox("Fournisseur", ["Tous", *_fournisseurs(session)], key="hist_fournisseur")
    recherche = c.text_input("Produit", placeholder="🔎  Code ou nom", key="hist_produit")
    if not isinstance(periode, (list, tuple)) or len(periode) != 2:
        return
    debut, fin = datetime.combine(periode[0], time.min), datetime.combine(periode[1], time.max)
    lots = session.query(LotStock).filter(LotStock.date.between(debut, fin)).order_by(LotStock.date.desc()).all()
    if fournisseur != "Tous":
        lots = [l for l in lots if l.fournisseur == fournisseur]
    if recherche:
        lots = [l for l in lots if recherche.lower() in f"{l.produit.reference} {l.produit.nom}".lower()]
    if not lots:
        st.caption("Aucune entrée sur cette période.")
        return
    df = pd.DataFrame(
        [
            {
                "Date": fmt_date(l.date),
                "Code": l.produit.reference,
                "Produit": l.produit.nom,
                "Quantité": f"{l.quantite} {l.produit.unite or ''}".strip(),
                "Reste en stock": l.restant,
                "Prix d'achat": l.prix_achat,
                "Prix de vente": l.prix_vente,
                "Total payé": l.prix_achat * l.quantite,
                "Fournisseur": l.fournisseur or "—",
            }
            for l in lots
        ]
    )
    config.kpis(
        [
            ("Entrées", len(lots), config.SECONDARY_BLUE, ""),
            ("Total des achats", fmt_money(df["Total payé"].sum()), config.WARNING_ORANGE, "sur la période"),
            ("Fournisseurs", len({l.fournisseur for l in lots if l.fournisseur}), config.MUTED, ""),
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            k: st.column_config.NumberColumn(format="localized")
            for k in ["Prix d'achat", "Prix de vente", "Total payé"]
        },
    )
    st.download_button(
        "⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "entrees_stock.csv", "text/csv"
    )
