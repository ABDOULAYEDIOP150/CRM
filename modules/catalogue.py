"""Produits & stock : la liste de référence de la boutique (code, nom, catégorie, unité, prix, seuil).

- Les prix se modifient directement dans le tableau, ou produit par produit (bouton « Modifier »).
- Stock : la colonne se modifie comme un inventaire (quantité comptée, écart noté dans le journal) ;
  les achats passent par « Achats », les ventes par la caisse.
- La base peut être importée d'un coup depuis un fichier Excel / CSV (bouton « Importer la base »).
"""

import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db import import_produits as I
from db.models import HistoriqueVente, Produit, VenteProduit, get_session
from db.stock import corriger_prix_lot, fixer_stock, generer_code
from db.utils import get_param
from modules.produits import mouvements
from modules.tableaux import styliser

AIDE_PRIX_ACHAT = (
    "Pour un produit déjà en stock, le prix d'achat vient de ses achats réels (entrées de stock) : "
    "il change à la prochaine entrée."
)


def categories(session, produits=None):
    """Catégories connues (une petite requête, ou la liste déjà chargée si on la donne)."""
    existantes = {p.categorie for p in produits} if produits is not None else {
        c for (c,) in session.query(Produit.categorie).distinct()}  # fmt: skip
    return sorted({c for c in existantes if c} | set(config.CATEGORIES_DEFAUT))


def unites(session, produits=None):
    existantes = {p.unite for p in produits} if produits is not None else {
        u for (u,) in session.query(Produit.unite).distinct()}  # fmt: skip
    return sorted({u for u in existantes if u} | set(config.UNITES))


def show_catalogue():
    with get_session() as session:
        config.entete("Produits & stock", "Prix, quantités et mouvements")
        produits = session.query(Produit).order_by(Produit.categorie, Produit.nom).all()

        if produits:
            seuil = int(get_param("seuil_stock"))
            ruptures = [p for p in produits if (p.stock or 0) <= 0 and p.lots]  # jamais acheté : pas une rupture
            faibles = [p for p in produits if 0 < (p.stock or 0) <= p.seuil(seuil)]
            en_stock = sum(1 for p in produits if (p.stock or 0) > 0)
            valeur = sum((p.prix_achat or 0) * max(p.stock or 0, 0) for p in produits)
            config.kpis(
                [
                    ("Produits", len(produits), config.SECONDARY_BLUE, f"{en_stock} en stock"),
                    ("Valeur du stock", fmt_money(valeur), config.SUCCESS_GREEN, "au prix d'achat"),
                    ("Ruptures", len(ruptures), config.DANGER_RED if ruptures else config.MUTED,
                     ", ".join(p.nom for p in ruptures[:2]) + ("…" if len(ruptures) > 2 else "")),
                    ("Stock faible", len(faibles), config.WARNING_ORANGE if faibles else config.MUTED,
                     ", ".join(p.nom for p in faibles[:2]) + ("…" if len(faibles) > 2 else "")),
                ]
            )  # fmt: skip
            st.write("")
            c = st.columns(5)
            if c[0].button("Ajouter un produit", type="primary", width="stretch", icon=":material/add:"):
                dialog_produit()
            if c[1].button("Modifier un produit", width="stretch", icon=":material/edit:"):
                dialog_modifier()
            config.bouton_page(c[2], "Nouvel achat", "Entrees", width="stretch", icon=":material/local_shipping:")
            if c[3].button("Importer", width="stretch", icon=":material/upload_file:"):
                st.session_state["base_import"] = True
                st.rerun()
            c[4].download_button("Exporter en Excel", I.modele_excel(produits), "produits.xlsx", width="stretch",
                                 icon=":material/download:")  # fmt: skip

        if st.session_state.get("base_import") or not produits:
            with config.carte():
                h, f = st.columns([5, 1], vertical_alignment="center")
                h.markdown("#### Importer des produits")
                if produits and f.button("Fermer", width="stretch"):
                    st.session_state["base_import"] = False
                    st.rerun()
                _import(session, produits)
            if not produits:
                return

        t1, t2 = st.tabs(["Produits", "Mouvements de stock"])
        with t1:
            filtre = st.text_input("Rechercher", placeholder="Rechercher un produit (code, nom, catégorie)",
                                   label_visibility="collapsed")  # fmt: skip
            _liste(session, produits, filtre)
        with t2:
            mouvements(session, produits)


def _liste(session, produits, filtre):
    tous = produits
    if filtre:
        f = filtre.lower()
        produits = [p for p in produits if f in f"{p.reference} {p.nom} {p.categorie}".lower()]
    if not produits:
        st.info("Aucun produit ne correspond à la recherche.")
        return
    df = pd.DataFrame(
        [
            {
                "id": p.id,
                "Code": p.reference or "",
                "Produit": p.nom,
                "Catégorie": p.categorie or "Divers",
                "Unité": p.unite or "pièce",
                "Prix de vente": int(p.prix or 0),
                "Prix d'achat": int(p.prix_achat or 0),
                "Marge": ((p.prix - p.prix_achat) / p.prix * 100) if p.prix and p.prix_achat else None,
                "Stock": p.stock or 0,
                "Seuil d'alerte": p.seuil_alerte,
            }
            for p in produits
        ]
    )
    df["Seuil d'alerte"] = df["Seuil d'alerte"].astype("Int64")
    devise = config.DEVISE
    edite = st.data_editor(
        styliser(df),
        hide_index=True,
        width="stretch",
        height=min(38 * len(df) + 40, 560),
        key="editeur_catalogue",
        disabled=["Marge"],
        column_config={
            "id": None,
            "Code": st.column_config.TextColumn(width="small"),
            "Produit": st.column_config.TextColumn(required=True, width="medium"),
            "Catégorie": st.column_config.SelectboxColumn(
                options=categories(session, tous), required=True, width="medium"
            ),
            "Unité": st.column_config.SelectboxColumn(options=unites(session, tous), required=True, width="small"),
            "Prix de vente": st.column_config.NumberColumn(
                f"Vente ({devise})", min_value=0, step=50, format="localized", width="small"
            ),
            "Prix d'achat": st.column_config.NumberColumn(
                f"Achat ({devise})",
                min_value=0,
                step=50,
                format="localized",
                width="small",
                help=AIDE_PRIX_ACHAT,
            ),
            "Marge": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=40, width="small"),
            "Stock": st.column_config.NumberColumn(
                "Stock ",
                min_value=0,
                step=1,
                width="small",
            ),  # fmt: skip
            "Seuil d'alerte": st.column_config.NumberColumn("Seuil", min_value=0, step=1, width="small"),
        },
    )
    colonnes = [c for c in df.columns if c not in ("Marge",)]
    norm = lambda d: d[colonnes].fillna(-1).astype(str).reset_index(drop=True)  # noqa: E731
    if norm(edite).equals(norm(df)):
        return
    _enregistrer(session, df, edite)


def _entier(v):
    return 0 if pd.isna(v) else int(v)


def _enregistrer(session, df, edite):
    """Résumé des changements (prix, inventaire…) puis enregistrement en un clic."""
    avant = df.set_index("id")
    stocks, prix, autres = [], 0, 0
    for _, r in edite.iterrows():
        a = avant.loc[r["id"]]
        if _entier(r["Stock"]) != _entier(a["Stock"]):
            stocks.append((r["Produit"], _entier(a["Stock"]), _entier(r["Stock"]), r["Unité"]))
        if _entier(r["Prix de vente"]) != _entier(a["Prix de vente"]) or _entier(r["Prix d'achat"]) != _entier(
            a["Prix d'achat"]
        ):
            prix += 1
        elif any(str(r[c]) != str(a[c]) for c in ("Code", "Produit", "Catégorie", "Unité", "Seuil d'alerte")):
            autres += 1
    lignes = []
    if stocks:
        lignes.append(f"**Inventaire** : {config.pluriel(len(stocks), 'stock corrigé', 'stocks corrigés')}")
        for n, a, b, u in stocks[:8]:
            if b > a:
                signe = f":green[+{b - a}]"
            elif b == 0:
                signe = f":red[{b - a} : le stock tombe à zéro]"
            else:
                signe = f":red[{b - a}]"
            lignes.append(f"  - {n} : {a} → **{b}** {u}  {signe}")
        if len(stocks) > 8:
            lignes.append(f"  - … et {config.pluriel(len(stocks) - 8, 'autre')}")
    if prix:
        lignes.append(f"**Prix modifiés** : {config.pluriel(prix, 'produit')}")
    if autres:
        lignes.append(f"Autres modifications : {config.pluriel(autres, 'produit')}")
    with config.carte():
        st.markdown("**Modifications à enregistrer**  \n" + "  \n".join(lignes))
        if not st.button("Enregistrer les modifications", type="primary"):
            return

    noms = [str(n).strip().lower() for n in edite["Produit"]]
    codes = [str(c).strip().upper() for c in edite["Code"] if str(c).strip()]
    if len(set(noms)) != len(noms) or not all(noms) or len(set(codes)) != len(codes):
        st.error("Chaque produit doit avoir un nom et un code uniques.")
        return
    ids = set(edite["id"])
    autres_produits = session.query(Produit.nom, Produit.reference).filter(Produit.id.notin_(ids)).all()
    if any(n.lower() in noms for n, _ in autres_produits) or any(
        (c or "").upper() in codes for _, c in autres_produits
    ):
        st.error("Un nom ou un code est déjà utilisé par un autre produit de la base.")
        return
    sans_prix = [
        r["Produit"] for _, r in edite.iterrows()
        if _entier(r["Stock"]) > _entier(avant.loc[r["id"]]["Stock"]) and _entier(r["Prix d'achat"]) == 0
    ]  # fmt: skip
    if sans_prix:
        st.error(
            "Indiquez d'abord le prix d'achat pour ajouter du stock (sinon le bénéfice serait faux) : "
            + ", ".join(sans_prix[:5])
        )
        return
    ignores, corriges = [], 0
    for _, r in edite.iterrows():
        p = session.get(Produit, int(r["id"]))
        p.nom, p.categorie, p.unite = str(r["Produit"]).strip(), r["Catégorie"], r["Unité"]
        p.reference = str(r["Code"]).strip().upper() or generer_code(session, p.nom)
        p.seuil_alerte = None if pd.isna(r["Seuil d'alerte"]) else int(r["Seuil d'alerte"])
        p.prix = _entier(r["Prix de vente"])
        pa = _entier(r["Prix d'achat"])
        if pa != int(p.prix_achat or 0):
            if (p.stock or 0) > 0:
                ignores.append(p.nom)
            else:
                p.prix_achat = pa  # avant l'inventaire : le stock ajouté est valorisé à ce prix
        compte = _entier(r["Stock"])
        if compte != (p.stock or 0):
            fixer_stock(session, p, compte, "Inventaire", "Inventaire (base produits)")
            corriges += 1
    session.commit()
    st.session_state.pop("editeur_catalogue", None)
    msg = "Produits mis à jour."
    if corriges:
        msg += f" Inventaire : {config.pluriel(corriges, 'stock corrigé', 'stocks corrigés')}."
    if ignores:
        msg += f" Prix d'achat inchangé pour {config.pluriel(len(ignores), 'produit')} en stock (il vient des achats)."
    config.flash(msg)
    st.rerun()


def _champs_produit(session, p=None, nom_propose=""):
    """Formulaire commun (ajout / modification). Retourne les valeurs saisies."""
    nom = st.text_input("Nom du produit *", value=p.nom if p else nom_propose, placeholder="Ex : Sable de mer")
    code = st.text_input(
        "Code",
        value=(p.reference if p else (generer_code(session, nom) if nom.strip() else "")),
    )
    a, b = st.columns(2)
    cats, uns = categories(session), unites(session)
    categorie = a.selectbox(
        "Catégorie", cats, index=cats.index(p.categorie if p and p.categorie in cats else "Divers"),
        accept_new_options=True,
    )  # fmt: skip
    unite = b.selectbox(
        "Unité", uns, index=uns.index(p.unite if p and p.unite in uns else "pièce"), accept_new_options=True,
        help="sac, m³, barre, kg…",
    )  # fmt: skip
    c, d = st.columns(2)
    pv = c.number_input(f"Prix de vente ({config.DEVISE})", min_value=0, step=50, value=int(p.prix or 0) if p else 0)
    en_stock = bool(p and (p.stock or 0) > 0)
    pa = d.number_input(
        f"Prix d'achat ({config.DEVISE})", min_value=0, step=50, value=int(p.prix_achat or 0) if p else 0,
        disabled=en_stock, help=AIDE_PRIX_ACHAT if en_stock else None,
    )  # fmt: skip
    if pv and pa and pv < pa:
        st.warning(f"Prix de vente inférieur au prix d'achat : perte de {fmt_money(pa - pv)} par {unite or 'pièce'}.")
    elif pv and pa:
        st.caption(f"Marge : {fmt_money(pv - pa)} par {unite or 'pièce'} ({(pv - pa) / pv:.0%})")
    seuil = st.number_input(
        "Alerter quand il reste…", min_value=0, step=1,
        value=int(p.seuil_alerte if p and p.seuil_alerte is not None else get_param("seuil_stock")),
    )  # fmt: skip
    return {"nom": nom.strip(), "code": (code or "").strip().upper(), "categorie": categorie or "Divers",
            "unite": unite or "pièce", "prix": pv, "prix_achat": pa, "seuil": seuil, "en_stock": en_stock}  # fmt: skip


def _verifier(session, v, produit_id=None):
    if not v["nom"]:
        return "Le nom est obligatoire."
    doublon = session.query(Produit).filter(Produit.nom.ilike(v["nom"])).first()
    if doublon and doublon.id != produit_id:
        return "Ce produit existe déjà dans la base."
    doublon = session.query(Produit).filter_by(reference=v["code"]).first() if v["code"] else None
    if doublon and doublon.id != produit_id:
        return f"Le code {v['code']} est déjà utilisé."
    return None


@st.dialog("Ajouter un produit à la base")
def dialog_produit(nom_propose=""):
    with get_session() as session:
        v = _champs_produit(session, nom_propose=nom_propose)
        apres = st.checkbox("Enregistrer un achat pour ce produit", value=False)
        if st.button("Ajouter à la base", type="primary", width="stretch"):
            erreur = _verifier(session, v)
            if erreur:
                st.error(erreur)
                return
            p = Produit(
                nom=v["nom"], reference=v["code"] or generer_code(session, v["nom"]), categorie=v["categorie"],
                unite=v["unite"], seuil_alerte=v["seuil"], stock=0, prix=v["prix"], prix_achat=v["prix_achat"],
            )  # fmt: skip
            session.add(p)
            session.commit()
            config.flash(f"{p.nom} ({p.reference}) ajouté à la base.")
            if apres:
                config.aller_a("Entrees", produit_cible=p.id)
            st.rerun()


@st.dialog("Modifier un produit")
def dialog_modifier(produit_id=None):
    with get_session() as session:
        produits = session.query(Produit).order_by(Produit.nom).all()
        par_id = {p.id: p for p in produits}
        pid = st.selectbox(
            "Produit",
            list(par_id),
            index=list(par_id).index(produit_id) if produit_id in par_id else None,
            placeholder="Tapez le début du nom ou le code",
            format_func=lambda i: f"{par_id[i].nom} ({par_id[i].reference}), {fmt_money(par_id[i].prix)}",
        )
        if pid is None:
            return
        p = par_id[pid]
        st.caption(f"En stock : {p.stock or 0} {p.unite or 'pièce'}")
        v = _champs_produit(session, p)
        a, b = st.columns(2)
        if a.button("Enregistrer", type="primary", width="stretch"):
            erreur = _verifier(session, v, p.id)
            if erreur:
                st.error(erreur)
                return
            p.nom, p.reference, p.categorie, p.unite = v["nom"], v["code"] or p.reference, v["categorie"], v["unite"]
            p.prix, p.seuil_alerte = v["prix"], v["seuil"]
            if not v["en_stock"]:
                p.prix_achat = v["prix_achat"]
            session.commit()
            st.session_state.pop("editeur_catalogue", None)
            config.flash(f"{p.nom} mis à jour.")
            st.rerun()
        utilise = (
            p.lots
            or session.query(VenteProduit).filter_by(produit_id=p.id).first()
            or session.query(HistoriqueVente).filter_by(produit_nom=p.nom).first()
        )
        if not utilise and b.button("Supprimer", width="stretch"):
            session.delete(p)
            session.commit()
            st.session_state.pop("editeur_catalogue", None)
            config.flash(f"{p.nom} supprimé de la base.")
            st.rerun()
        if utilise:
            b.caption("Déjà utilisé, non supprimable.")


@st.dialog("Corriger le prix", width="large")
def dialog_prix(produit_id):
    """Le produit concerné directement : son prix de vente et ses prix d'achat, modifiables ici."""
    with get_session() as session:
        p = session.get(Produit, produit_id)
        if p is None:
            st.error("Produit introuvable.")
            return
        unite = p.unite or "pièce"
        st.markdown(f"#### {p.nom}")
        st.caption(f"{p.reference} · en stock : {p.stock or 0} {config.unite_pl(p.stock or 0, unite)}")

        lots = list(reversed(p.lots[-8:]))
        st.markdown("##### Prix d'achat")
        if lots:
            df = pd.DataFrame(
                [
                    {
                        "id": l.id,
                        "Date": l.date.strftime("%d/%m/%Y"),
                        "Fournisseur": l.fournisseur or "",
                        "Quantité": l.quantite,
                        "Reste": l.restant,
                        "Prix d'achat": int(l.prix_achat),
                    }
                    for l in lots
                ]
            )
            edite = st.data_editor(
                df,
                hide_index=True,
                width="stretch",
                key=f"lots_prix_{p.id}",
                disabled=["Date", "Fournisseur", "Quantité", "Reste"],
                column_order=["Date", "Fournisseur", "Quantité", "Reste", "Prix d'achat"],
                column_config={
                    "Prix d'achat": st.column_config.NumberColumn(
                        f"Prix d'achat / {unite}", min_value=0, step=50, format="localized"
                    )
                },
            )
            st.caption(
                "Prix mal saisi : tapez le bon prix dans la ligne. Deux fournisseurs, deux prix : laissez tel quel."
            )
        else:
            edite = None
            st.caption("Aucun achat enregistré pour ce produit.")

        nouveaux = {}
        if edite is not None:
            for _, r in edite.iterrows():
                v = _entier(r["Prix d'achat"])
                lot = next(l for l in lots if l.id == r["id"])
                if v != int(lot.prix_achat):
                    nouveaux[lot.id] = v
        for l in (x for x in lots if p.prix and nouveaux.get(x.id, x.prix_achat) > p.prix):
            st.markdown(
                f"<div class='crm-alert' style='--c:{config.DANGER_RED}'><b>Achat du {l.date:%d/%m/%Y}</b>"
                f"{' · ' + l.fournisseur if l.fournisseur else ''} : {fmt_money(l.prix_achat)} par {unite},"
                f" plus cher que le prix de vente</div>",
                unsafe_allow_html=True,
            )
        restants = [(l.restant, nouveaux.get(l.id, l.prix_achat)) for l in p.lots if l.restant > 0]
        cout = (
            round(sum(q * c for q, c in restants) / sum(q for q, _ in restants))
            if restants
            else (next(iter(nouveaux.values())) if nouveaux else int(p.prix_achat or 0))
        )

        st.markdown("##### Prix de vente")
        taux = float(get_param("marge_defaut") or 20)
        propose = int(round(cout * (1 + taux / 100), -1))
        a, b = st.columns([1, 1.4], vertical_alignment="bottom")
        pv = a.number_input(
            f"Prix de vente / {unite}", min_value=0, step=50, value=int(p.prix or 0), key=f"pv_corr_{p.id}"
        )
        b.caption(f"Coût d'achat : {fmt_money(cout)}. Avec {taux:.0f} % de marge : {fmt_money(propose)}.")
        if pv and pv < cout:
            st.error(f"Encore à perte : {fmt_money(cout - pv)} perdus par {unite}.")
        elif pv:
            st.success(f"Bénéfice : {fmt_money(pv - cout)} par {unite} ({(pv - cout) / pv:.0%}).")

        if st.button("Enregistrer", type="primary", width="stretch", icon=":material/check:", key=f"ok_prix_{p.id}"):
            for lot in lots:
                if lot.id in nouveaux:
                    corriger_prix_lot(session, lot, nouveaux[lot.id])
            p.prix = pv
            session.commit()
            st.session_state.pop("editeur_catalogue", None)
            config.flash(f"Prix de {p.nom} corrigé.")
            st.rerun()


# ------------------------------------------------------------------ Import Excel
def _import(session, produits):
    st.download_button("Télécharger un modèle vide", I.modele_excel(), "modele_produits.xlsx")
    fichier = st.file_uploader("Déposez votre fichier Excel ou CSV", type=["xlsx", "xls", "csv"], key="fichier_import")
    if fichier is None:
        return
    try:
        df = I.lire_fichier(fichier.name, fichier.getvalue())
        lignes, cols = I.analyser(session, df)
    except Exception as e:  # fichier illisible ou colonne du nom absente
        st.error(f"Impossible de lire ce fichier : {e}")
        return
    compte = {k: sum(l["action"] == k for l in lignes) for k in (I.NOUVEAU, I.MAJ, I.INCHANGE, I.ERREUR)}
    config.kpis(
        [
            ("Nouveaux produits", compte[I.NOUVEAU], config.SUCCESS_GREEN, ""),
            ("Mises à jour", compte[I.MAJ], config.SECONDARY_BLUE, ""),
            ("Inchangés", compte[I.INCHANGE], config.MUTED, ""),
            ("Erreurs (ignorées)", compte[I.ERREUR], config.DANGER_RED if compte[I.ERREUR] else config.MUTED, ""),
        ]
    )
    st.dataframe(
        styliser(
            pd.DataFrame(
                [
                    {
                        "Ligne": l["ligne"],
                        "Produit": l["nom"],
                        "Action": l["action"],
                        "Détail": l["detail"],
                    }
                    for l in lignes
                ]
            )
        ),
        hide_index=True,
        width="stretch",
    )
    mode = ""
    if "stock" in cols:
        mode = st.radio(
            "Pour les produits déjà en stock, la colonne Stock est…",
            ["Une quantité reçue à ajouter (arrivage)", "Le stock total compté (inventaire)"],
            horizontal=True,
        )
    a_faire = compte[I.NOUVEAU] + compte[I.MAJ]
    if st.button(f"Importer {config.pluriel(a_faire, 'produit')}", type="primary", disabled=a_faire == 0):
        res = I.appliquer(session, lignes, "remplacer" if mode.startswith("Le stock total") else "ajouter")
        session.commit()
        st.session_state.pop("editeur_catalogue", None)
        st.session_state.pop("fichier_import", None)
        st.session_state["base_import"] = False
        config.flash(f"Import terminé : {res[I.NOUVEAU]} nouveaux, {res[I.MAJ]} mis à jour.")
        st.rerun()
