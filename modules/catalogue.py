"""📚 Catalogue produits : la liste de référence (code, nom, catégorie, unité). Ni prix, ni quantité ici :
ils se saisissent à chaque entrée de stock."""

import pandas as pd
import streamlit as st

import config
from db import import_produits as I
from db.models import Produit, get_session
from db.stock import generer_code
from db.utils import get_param


def categories(session):
    existantes = {p.categorie for p in session.query(Produit) if p.categorie}
    return sorted(existantes | set(config.CATEGORIES_DEFAUT))


def unites(session):
    return sorted(set(config.UNITES) | {p.unite for p in session.query(Produit) if p.unite})


def show_catalogue():
    with get_session() as session:
        config.entete(
            "Catalogue produits",
            "La liste de vos produits avec leur code. Les prix et les quantités se saisissent dans « Entrée de stock ».",
        )
        produits = session.query(Produit).order_by(Produit.categorie, Produit.nom).all()
        a, b, c = st.columns([1.2, 1.4, 3], vertical_alignment="bottom")
        if a.button("➕ Nouveau produit", type="primary", use_container_width=True):
            dialog_produit()
        if b.button("📥 Entrée de stock", use_container_width=True):
            config.aller_a("Entrees")
        filtre = c.text_input("Filtrer", placeholder="🔎  Code, nom ou catégorie…", label_visibility="collapsed")
        t1, t2 = st.tabs(["📋 Liste des produits", "📊 Importer depuis Excel"])
        with t1:
            _liste(session, produits, filtre)
        with t2:
            _import(session, produits)


def _liste(session, produits, filtre):
    if not produits:
        st.info("Le catalogue est vide. Ajoutez un produit ou importez votre liste depuis Excel.")
        return
    if filtre:
        f = filtre.lower()
        produits = [p for p in produits if f in f"{p.reference} {p.nom} {p.categorie}".lower()]
    seuil = int(get_param("seuil_stock"))
    df = pd.DataFrame(
        [
            {
                "id": p.id,
                "Code": p.reference or "",
                "Produit": p.nom,
                "Catégorie": p.categorie or "Divers",
                "Unité": p.unite or "pièce",
                "Seuil d'alerte": p.seuil_alerte,
                "Achats enregistrés": len(p.lots),
            }
            for p in produits
        ]
    )
    df["Seuil d'alerte"] = df["Seuil d'alerte"].astype("Int64")
    st.caption(f"{len(df)} produit(s) · double-cliquez sur une case pour la modifier · seuil vide = {seuil} (général)")
    edite = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        key="editeur_catalogue",
        disabled=["Achats enregistrés"],
        column_config={
            "id": None,
            "Code": st.column_config.TextColumn(width="small", help="Code court et unique (ex. SAB-001)"),
            "Produit": st.column_config.TextColumn(required=True, width="medium"),
            "Catégorie": st.column_config.SelectboxColumn(options=categories(session), required=True),
            "Unité": st.column_config.SelectboxColumn(options=unites(session), required=True, width="small"),
            "Seuil d'alerte": st.column_config.NumberColumn(min_value=0, step=1, width="small"),
        },
    )
    norm = lambda d: d.fillna(-1).astype(str).reset_index(drop=True)  # noqa: E731
    if norm(edite).equals(norm(df)):
        return
    st.warning("Des modifications ne sont pas encore enregistrées.")
    if st.button("💾 Enregistrer les modifications", type="primary"):
        noms = [str(n).strip().lower() for n in edite["Produit"]]
        codes = [str(c).strip().upper() for c in edite["Code"] if str(c).strip()]
        if len(set(noms)) != len(noms) or not all(noms) or len(set(codes)) != len(codes):
            st.error("Chaque produit doit avoir un nom et un code uniques.")
            return
        for _, r in edite.iterrows():
            p = session.get(Produit, int(r["id"]))
            p.nom, p.categorie, p.unite = str(r["Produit"]).strip(), r["Catégorie"], r["Unité"]
            p.reference = str(r["Code"]).strip().upper() or generer_code(session, p.nom)
            p.seuil_alerte = None if pd.isna(r["Seuil d'alerte"]) else int(r["Seuil d'alerte"])
        session.commit()
        st.session_state.pop("editeur_catalogue", None)
        config.flash("Catalogue mis à jour.")
        st.rerun()


@st.dialog("➕ Nouveau produit dans le catalogue")
def dialog_produit(nom_propose=""):
    st.caption(
        "Seulement l'identité du produit. Le prix d'achat, le prix de vente et la quantité "
        "se saisissent ensuite dans « Entrée de stock »."
    )
    with get_session() as session:
        nom = st.text_input("Nom du produit *", value=nom_propose, placeholder="Ex : Sable de mer")
        code = st.text_input(
            "Code",
            value=generer_code(session, nom) if nom.strip() else "",
            help="Proposé automatiquement, modifiable (ex. SAB-001)",
        )
        a, b = st.columns(2)
        cats = categories(session)
        categorie = a.selectbox("Catégorie", cats, index=cats.index("Divers"), accept_new_options=True)
        unite = b.selectbox(
            "Unité",
            unites(session),
            accept_new_options=True,
            index=unites(session).index("pièce"),
            help="sac, m³, barre, kg…",
        )
        seuil = st.number_input("Alerter quand il reste…", min_value=0, step=1, value=int(get_param("seuil_stock")))
        apres = st.checkbox("Faire tout de suite une entrée de stock pour ce produit", value=True)
        if st.button("Ajouter au catalogue", type="primary", use_container_width=True):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
                return
            if session.query(Produit).filter(Produit.nom.ilike(nom.strip())).first():
                st.error("Ce produit existe déjà dans le catalogue.")
                return
            code = (code or generer_code(session, nom)).strip().upper()
            if session.query(Produit).filter_by(reference=code).first():
                st.error(f"Le code {code} est déjà utilisé.")
                return
            p = Produit(
                nom=nom.strip(),
                reference=code,
                categorie=categorie or "Divers",
                unite=unite or "pièce",
                seuil_alerte=seuil,
                stock=0,
                prix_achat=0,
            )
            session.add(p)
            session.commit()
            config.flash(f"{p.nom} ({p.reference}) ajouté au catalogue.")
            if apres:
                config.aller_a("Entrees", produit_cible=p.id)
            st.rerun()


# ------------------------------------------------------------------ Import Excel
def _import(session, produits):
    st.markdown(
        "**Pas besoin de tout saisir à la main.** Remplissez un fichier Excel (ou reprenez la liste de votre "
        "fournisseur) puis importez-le. Seul le **nom** est obligatoire ; si le fichier contient aussi la "
        "quantité et le prix d'achat, une **entrée de stock** est créée automatiquement."
    )
    a, b = st.columns(2)
    a.download_button(
        "⬇️ Télécharger le modèle Excel", I.modele_excel(), "modele_produits.xlsx", use_container_width=True
    )
    if produits:
        b.download_button(
            "⬇️ Exporter mon catalogue (pour le modifier dans Excel)",
            I.modele_excel(produits),
            "mon_catalogue.xlsx",
            use_container_width=True,
        )
    with st.expander("Comment remplir le fichier ?"):
        st.markdown(
            "- Colonnes reconnues automatiquement : *Nom / Désignation / Article*, *Code / Référence*, *Catégorie / "
            "Famille*, *Unité*, *Stock / Qté*, *Prix d'achat / PA*, *Prix de vente / PV*, *Seuil*.\n"
            "- Les montants peuvent s'écrire « 4 600 », « 4600 » ou « 4 600 FCFA ».\n"
            "- Un produit déjà présent (même **code**, sinon même **nom**) est mis à jour, jamais dupliqué.\n"
            "- Sans code, un code est créé automatiquement (ex. SAB-001)."
        )
    fichier = st.file_uploader("Déposez votre fichier Excel ou CSV", type=["xlsx", "xls", "csv"], key="fichier_import")
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
    config.kpis(
        [
            ("Nouveaux produits", compte[I.NOUVEAU], config.SUCCESS_GREEN, ""),
            ("Mises à jour", compte[I.MAJ], config.SECONDARY_BLUE, ""),
            ("Inchangés", compte[I.INCHANGE], config.MUTED, ""),
            ("Erreurs (ignorées)", compte[I.ERREUR], config.DANGER_RED if compte[I.ERREUR] else config.MUTED, ""),
        ]
    )
    icones = {I.NOUVEAU: "🟢", I.MAJ: "🔵", I.INCHANGE: "⚪", I.ERREUR: "🔴"}
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Ligne": l["ligne"],
                    "Produit": l["nom"],
                    "Action": f"{icones[l['action']]} {l['action']}",
                    "Détail": l["detail"],
                }
                for l in lignes
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    mode = ""
    if "stock" in cols:
        mode = st.radio(
            "Pour les produits déjà en stock, la colonne Stock est…",
            ["Une quantité reçue à ajouter (arrivage)", "Le stock total compté (inventaire)"],
            horizontal=True,
        )
    a_faire = compte[I.NOUVEAU] + compte[I.MAJ]
    if st.button(f"✅ Importer {a_faire} produit(s)", type="primary", disabled=a_faire == 0):
        res = I.appliquer(session, lignes, "remplacer" if mode.startswith("Le stock total") else "ajouter")
        session.commit()
        st.session_state.pop("editeur_catalogue", None)
        st.session_state.pop("fichier_import", None)
        config.flash(f"Import terminé : {res[I.NOUVEAU]} créé(s), {res[I.MAJ]} mis à jour.")
        st.rerun()
