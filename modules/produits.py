"""Produits & stock : modification directe dans le tableau, ajout, réapprovisionnement."""

import pandas as pd
import streamlit as st

import config
from config import fmt_money
from db import import_produits as I
from db.models import MouvementStock, Produit, get_session
from db.stock import fixer_stock, mouvement
from db.utils import get_param


def _categories(session):
    existantes = {p.categorie for p in session.query(Produit) if p.categorie}
    return sorted(existantes | set(config.CATEGORIES_DEFAUT))


def show_produits():
    seuil = int(get_param("seuil_stock"))
    with get_session() as session:
        config.entete(
            "Produits & stock",
            "Votre catalogue : ajoutez, importez depuis Excel, suivez chaque entrée et sortie de stock.",
        )
        produits = session.query(Produit).order_by(Produit.categorie, Produit.nom).all()
        ruptures = [p for p in produits if (p.stock or 0) <= 0]
        faibles = [p for p in produits if 0 < (p.stock or 0) <= p.seuil(seuil)]
        config.kpis(
            [
                (
                    "Produits",
                    len(produits),
                    config.SECONDARY_BLUE,
                    f"{len({p.categorie for p in produits})} catégories",
                ),
                (
                    "Valeur du stock",
                    fmt_money(sum((p.prix_achat or p.prix or 0) * max(p.stock or 0, 0) for p in produits)),
                    config.SUCCESS_GREEN,
                    "au prix d'achat",
                ),
                (
                    "Ruptures",
                    len(ruptures),
                    config.DANGER_RED if ruptures else config.MUTED,
                    ", ".join(p.nom for p in ruptures[:3]),
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
        t1, t2, t3 = st.tabs(["📋 Catalogue", "📥 Importer depuis Excel", "📜 Mouvements de stock"])
        with t1:
            _catalogue(session, produits, seuil)
        with t2:
            _import(session, produits)
        with t3:
            _mouvements(session, produits)


def _catalogue(session, produits, seuil):
    a, b, c = st.columns([1.2, 1.6, 3], vertical_alignment="bottom")
    if a.button("➕ Nouveau produit", type="primary", use_container_width=True):
        _dialog_produit(_categories(session))
    if b.button("📥 Réception de marchandise", use_container_width=True):
        _dialog_reception([(p.id, p.nom, p.unite) for p in produits])
    filtre = c.text_input("Filtrer", placeholder="🔎  Filtrer les produits…", label_visibility="collapsed")
    if not produits:
        st.info("Aucun produit pour l'instant.")
        return
    if filtre:
        produits = [p for p in produits if filtre.lower() in f"{p.nom} {p.categorie} {p.reference}".lower()]

    def statut(p):
        if (p.stock or 0) <= 0:
            return "🔴 Rupture"
        return "🟠 Faible" if p.stock <= p.seuil(seuil) else "🟢 OK"

    df = pd.DataFrame(
        [
            {
                "id": p.id,
                "Produit": p.nom,
                "Catégorie": p.categorie or "Divers",
                "Unité": p.unite or "pièce",
                "Prix de vente": int(p.prix or 0),
                "Prix d'achat": int(p.prix_achat or 0),
                "Stock": int(p.stock or 0),
                "Seuil d'alerte": p.seuil_alerte,
                "État": statut(p),
            }
            for p in produits
        ]
    )
    df["Seuil d'alerte"] = df["Seuil d'alerte"].astype("Int64")
    st.caption(f"Seuil d'alerte vide = seuil général ({seuil}). Double-cliquez sur une case pour la modifier.")
    edite = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        key="editeur_produits",
        disabled=["État"],
        column_config={
            "id": None,
            "Produit": st.column_config.TextColumn(required=True, width="medium"),
            "Catégorie": st.column_config.SelectboxColumn(options=_categories(session), required=True),
            "Unité": st.column_config.SelectboxColumn(
                options=sorted(set(config.UNITES) | {p.unite for p in produits if p.unite}),
                required=True,
                width="small",
            ),
            "Prix de vente": st.column_config.NumberColumn(min_value=0, step=50, format="localized"),
            "Prix d'achat": st.column_config.NumberColumn(
                min_value=0, step=50, format="localized", help="Sert à calculer votre bénéfice"
            ),
            "Stock": st.column_config.NumberColumn(min_value=0, step=1, width="small"),
            "Seuil d'alerte": st.column_config.NumberColumn(
                min_value=0, step=1, width="small", help="Alerte quand le stock descend à ce niveau"
            ),
        },
    )
    if not _norm(edite).equals(_norm(df)):
        st.warning("Des modifications ne sont pas encore enregistrées.")
        if st.button("💾 Enregistrer les modifications", type="primary"):
            noms = [str(n).strip() for n in edite["Produit"]]
            if len(set(noms)) != len(noms) or not all(noms):
                st.error("Deux produits ne peuvent pas avoir le même nom, et le nom est obligatoire.")
                return
            for _, r in edite.iterrows():
                p = session.get(Produit, int(r["id"]))
                p.nom, p.categorie, p.unite = str(r["Produit"]).strip(), r["Catégorie"], r["Unité"]
                p.prix, p.prix_achat = r["Prix de vente"], r["Prix d'achat"]
                fixer_stock(session, p, int(r["Stock"]), "Correction", "Modification dans le tableau")
                p.seuil_alerte = None if pd.isna(r["Seuil d'alerte"]) else int(r["Seuil d'alerte"])
            session.commit()
            st.session_state.pop("editeur_produits", None)
            config.flash("Produits mis à jour.")
            st.rerun()


def _norm(d):
    return d.fillna(-1).astype(str).reset_index(drop=True)


@st.dialog("➕ Nouveau produit")
def _dialog_produit(categories):
    with st.form("nouveau_produit"):
        nom = st.text_input("Nom du produit *", placeholder="Ex : Ciment CPJ 45 - 50 kg")
        a, b = st.columns(2)
        categorie = a.selectbox(
            "Catégorie",
            categories,
            index=categories.index("Divers"),
            accept_new_options=True,
            help="Choisissez ou tapez une nouvelle catégorie",
        )
        unite = b.selectbox("Unité de vente", config.UNITES)
        a, b = st.columns(2)
        prix = a.number_input("Prix de vente (FCFA)", min_value=0, step=50)
        achat = b.number_input("Prix d'achat (FCFA)", min_value=0, step=50, help="Pour calculer le bénéfice")
        a, b = st.columns(2)
        stock = a.number_input("Quantité en stock", min_value=0, step=1)
        seuil = b.number_input("Alerter quand il reste…", min_value=0, step=1, value=int(get_param("seuil_stock")))
        if st.form_submit_button("Ajouter", type="primary", use_container_width=True):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
                return
            with get_session() as session:
                if session.query(Produit).filter_by(nom=nom.strip()).first():
                    st.error("Ce produit existe déjà.")
                    return
                p = Produit(
                    nom=nom.strip(),
                    categorie=categorie or "Divers",
                    unite=unite,
                    prix=prix,
                    prix_achat=achat,
                    stock=0,
                    seuil_alerte=seuil,
                )
                session.add(p)
                mouvement(session, p, stock, "Création", "Stock initial")
                session.commit()
            config.flash(f"Produit {nom} ajouté.")
            st.rerun()


@st.dialog("📥 Réception de marchandise")
def _dialog_reception(produits):
    st.caption("Ajoutez au stock ce que vous venez de recevoir du fournisseur.")
    noms = {pid: f"{nom} ({unite or 'pièce'})" for pid, nom, unite in produits}
    with st.form("reception"):
        pid = st.selectbox(
            "Produit", list(noms), format_func=noms.get, index=None, placeholder="Tapez les premières lettres…"
        )
        qte = st.number_input("Quantité reçue", min_value=1, step=1)
        achat = st.number_input("Nouveau prix d'achat (laisser 0 pour ne pas changer)", min_value=0, step=50)
        if st.form_submit_button("Ajouter au stock", type="primary", use_container_width=True):
            if pid is None:
                st.error("Choisissez un produit.")
                return
            with get_session() as session:
                p = session.get(Produit, pid)
                mouvement(session, p, qte, "Réception", "Arrivage fournisseur")
                if achat:
                    p.prix_achat = achat
                session.commit()
                config.flash(f"+{qte} {p.unite or 'pièce'}(s) de {p.nom} · stock : {p.stock}")
            st.session_state.pop("editeur_produits", None)
            st.rerun()


# ------------------------------------------------------------------ Import Excel
def _import(session, produits):
    st.markdown(
        "**Pas besoin de tout saisir à la main.** Remplissez un fichier Excel (ou reprenez la liste de votre "
        "fournisseur), puis importez-le : les nouveaux produits sont créés, ceux qui existent déjà sont mis à jour."
    )
    a, b = st.columns(2)
    a.download_button("⬇️ Télécharger le modèle Excel (vide, avec exemples)", I.modele_excel(),
                      "modele_produits.xlsx", use_container_width=True)  # fmt: skip
    if produits:
        b.download_button("⬇️ Exporter mon catalogue pour le modifier dans Excel", I.modele_excel(produits),
                          "mon_catalogue.xlsx", use_container_width=True)  # fmt: skip
    with st.expander("Comment remplir le fichier ?"):
        st.markdown(
            "- **Nom** et **Prix de vente** obligatoires pour un nouveau produit ; les autres colonnes sont facultatives.\n"
            "- Les noms de colonnes sont reconnus automatiquement : *Désignation*, *Article*, *Qté*, *PV*, *PA*, "
            "*Famille*, *Code*…\n"
            "- Les montants peuvent être écrits « 4 600 », « 4600 » ou « 4 600 FCFA ».\n"
            "- Un produit qui existe déjà (même **référence**, sinon même **nom**) est **mis à jour**, pas dupliqué.\n"
            "- Fichiers acceptés : Excel (.xlsx) ou CSV."
        )
    fichier = st.file_uploader("Déposez votre fichier ici", type=["xlsx", "xls", "csv"], key="fichier_import")
    if fichier is None:
        return
    try:
        df = I.lire_fichier(fichier.name, fichier.getvalue())
        lignes, cols = I.analyser(session, df)
    except Exception as e:  # fichier illisible ou colonne du nom absente
        st.error(f"Impossible de lire ce fichier : {e}")
        return
    st.caption("Colonnes reconnues : " + ", ".join(f"{I.ENTETES_MODELE[k]} ← « {v} »" for k, v in cols.items()))
    compte = {k: sum(l["action"] == k for l in lignes) for k in (I.NOUVEAU, I.MAJ, I.INCHANGE, I.ERREUR)}
    config.kpis([
        ("Nouveaux produits", compte[I.NOUVEAU], config.SUCCESS_GREEN, ""),
        ("Mises à jour", compte[I.MAJ], config.SECONDARY_BLUE, ""),
        ("Inchangés", compte[I.INCHANGE], config.MUTED, ""),
        ("Erreurs (ignorées)", compte[I.ERREUR], config.DANGER_RED if compte[I.ERREUR] else config.MUTED, ""),
    ])  # fmt: skip
    icones = {I.NOUVEAU: "🟢", I.MAJ: "🔵", I.INCHANGE: "⚪", I.ERREUR: "🔴"}
    st.dataframe(pd.DataFrame([{"Ligne": l["ligne"], "Produit": l["nom"], "Action": f"{icones[l['action']]} {l['action']}",
                                "Détail": l["detail"]} for l in lignes]),
                 hide_index=True, use_container_width=True)  # fmt: skip
    if "stock" in cols:
        mode = st.radio("La colonne Stock correspond à…",
                        ["Le stock total actuel (inventaire)", "Une quantité reçue à ajouter (arrivage)"],
                        horizontal=True)  # fmt: skip
    else:
        mode = ""
    a_faire = compte[I.NOUVEAU] + compte[I.MAJ]
    if st.button(f"✅ Importer {a_faire} produit(s)", type="primary", disabled=a_faire == 0):
        res = I.appliquer(session, lignes, "ajouter" if mode.startswith("Une quantité") else "remplacer")
        session.commit()
        st.session_state.pop("editeur_produits", None)
        st.session_state.pop("fichier_import", None)
        config.flash(f"Import terminé : {res[I.NOUVEAU]} créé(s), {res[I.MAJ]} mis à jour.")
        st.rerun()


# ------------------------------------------------------------------ Journal du stock
def _mouvements(session, produits):
    st.markdown(
        "Chaque vente, réception, correction ou import est enregistré ici : vous savez toujours pourquoi un stock a changé."
    )
    par_id = {p.id: p.nom for p in produits}
    a, b = st.columns([2, 1])
    choix = a.selectbox("Produit", [None, *par_id], format_func=lambda i: "Tous les produits" if i is None else par_id[i],
                        key="mvt_produit")  # fmt: skip
    types = b.multiselect("Type", ["Vente", "Réception", "Correction", "Import", "Création"], placeholder="Tous")
    q = session.query(MouvementStock).order_by(MouvementStock.date.desc(), MouvementStock.id.desc())
    if choix is not None:
        q = q.filter(MouvementStock.produit_id == choix)
    if types:
        q = q.filter(MouvementStock.type.in_(types))
    mvts = q.limit(500).all()
    if not mvts:
        st.info("Aucun mouvement enregistré pour l'instant.")
        return
    df = pd.DataFrame([{"Date": m.date.strftime("%d/%m/%Y %H:%M"), "Produit": m.produit.nom, "Type": m.type,
                        "Quantité": f"{m.quantite:+d} {m.produit.unite or ''}".strip(), "Stock après": m.stock_apres,
                        "Détail": m.note} for m in mvts])  # fmt: skip
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "mouvements_stock.csv",
                       "text/csv")  # fmt: skip
