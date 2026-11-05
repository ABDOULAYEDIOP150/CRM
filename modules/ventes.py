"""Caisse : recherche et cartes produits à gauche, ticket (client, panier, règlement) fixe à droite."""

from datetime import date, datetime, timedelta

import streamlit as st
from sqlalchemy import func

import config
from config import CLIENT_PASSAGE, fmt_date, fmt_money
from db import dettes as D
from db.models import Client, HistoriqueVente, Paiement, Produit, Vente, VenteProduit, get_session, memoire
from db.stock import ErreurStock, sortie_stock
from db.utils import client_de_passage, get_params
from modules import documents, ui

COMPTANT = "Payé comptant"
DETTE = "À crédit (dette)"
FILTRES = ["Tous", "Disponibles", "Plus vendus"]
PAR_PAGE = 24
MODES_RAPIDES = ["Espèces", "Wave", "Orange Money", "Autre"]


def _panier():
    return st.session_state.setdefault("panier", {})  # {produit_id: quantité}


def _vider_panier():
    for cle in [k for k in st.session_state if str(k).startswith("q_")]:
        del st.session_state[cle]
    st.session_state["panier"] = {}


def _ajouter(pid):
    """Callback : +1 au panier (avant la relance, donc carte et ticket sont à jour au même affichage)."""
    panier = _panier()
    with get_session() as s:
        p = s.get(Produit, pid)
        if p and (p.stock or 0) > panier.get(pid, 0):
            panier[pid] = panier.get(pid, 0) + 1
            st.session_state[f"q_{pid}"] = panier[pid]
            st.session_state["toast_vente"] = (f"{p.nom} ajouté au panier", ":material/add_shopping_cart:")
        elif p:
            st.session_state["toast_vente"] = (f"Plus de stock pour {p.nom}", ":material/warning:")


def _changer(pid, delta, stock):
    """Callback des boutons − / + du panier."""
    cle = f"q_{pid}"
    q = min(max(int(st.session_state.get(cle, _panier().get(pid, 1))) + delta, 1), max(int(stock or 1), 1))
    st.session_state[cle] = q
    _panier()[pid] = q


def _retirer(pid):
    _panier().pop(pid, None)
    st.session_state.pop(f"q_{pid}", None)


def _ajouter_depuis_recherche():
    """Appelé quand on choisit un produit dans la recherche : ajout au panier puis remise à zéro."""
    pid = st.session_state.get("recherche_produit")
    if pid is not None:
        _ajouter(pid)
    st.session_state["recherche_produit"] = None


def _plus_vendus():
    """Quantités vendues par produit sur 90 jours (une requête, gardée en mémoire)."""

    def calcul():
        depuis = datetime.now() - timedelta(days=90)
        with get_session() as s:
            q = (
                s.query(VenteProduit.produit_id, func.sum(VenteProduit.quantite))
                .join(Vente, Vente.id == VenteProduit.vente_id)
                .filter(Vente.date >= depuis)
                .group_by(VenteProduit.produit_id)
            )
            return dict(q.all())

    return memoire(("plus_vendus", date.today()), calcul)


def show_ventes():
    if "toast_vente" in st.session_state:
        texte, icone = st.session_state.pop("toast_vente")
        st.toast(texte, icon=icone)
    with get_session() as session:
        if st.session_state.get("derniere_vente"):
            _confirmation(session, st.session_state["derniere_vente"])
            return
        config.entete("Nouvelle vente", "Produits, client, règlement")
        gauche, droite = st.columns([1.85, 1], gap="medium")
        with gauche:
            _catalogue(session)
        with droite:
            _ticket(session)


# ------------------------------------------------------------------ Catalogue
def _catalogue(session):
    panier = _panier()
    tous = session.query(Produit).order_by(Produit.nom).all()
    if not tous:
        st.info("Aucun produit dans la base.")
        config.bouton_page(st, "Ajouter des produits", "Catalogue")
        return
    par_id = {p.id: p for p in tous}

    r1, r2 = st.columns([1.9, 1.7], vertical_alignment="center")
    r1.selectbox(
        "Rechercher un produit",
        list(par_id),
        index=None,
        key="recherche_produit",
        on_change=_ajouter_depuis_recherche,
        placeholder="Rechercher un produit (nom ou code)",
        format_func=lambda i: (
            f"{par_id[i].nom}, {fmt_money(par_id[i].prix)}, stock {par_id[i].stock} {par_id[i].unite or 'pièce'}"
        ),
        label_visibility="collapsed",
    )
    filtre = (
        r2.segmented_control("Filtre", FILTRES, default="Tous", key="filtre_vente", label_visibility="collapsed")
        or "Tous"
    )
    categories = sorted({p.categorie or "Divers" for p in tous})
    couleurs = {c: ui.PALETTE[i % len(ui.PALETTE)] for i, c in enumerate(categories)}
    cat = None
    if len(categories) > 1:
        cat = st.pills("Catégorie", categories, key="cat_vente", label_visibility="collapsed")

    produits = [p for p in tous if cat is None or (p.categorie or "Divers") == cat]
    if filtre == "Disponibles":
        produits = [p for p in produits if (p.stock or 0) > 0]
    if filtre == "Plus vendus":
        vendus = _plus_vendus()
        produits = sorted((p for p in produits if p.id in vendus), key=lambda p: -vendus[p.id])
    else:
        produits.sort(key=lambda p: ((p.stock or 0) <= 0, p.nom.lower()))  # disponibles d'abord
    if not produits:
        st.info("Aucun produit pour ce filtre.")
        return

    seuil = int(get_params()["seuil_stock"])
    nb = st.session_state.get("vente_nb", PAR_PAGE)
    cols = st.columns(4, gap="small")
    for i, p in enumerate(produits[:nb]):
        dans_panier = panier.get(p.id, 0)
        dispo = (p.stock or 0) - dans_panier
        with cols[i % 4].container(key=f"pv_{p.id}"):
            st.markdown(
                ui.carte_produit(p, dans_panier, couleurs[p.categorie or "Divers"], seuil), unsafe_allow_html=True
            )
            st.button(
                "Ajouter",
                key=f"add_{p.id}",
                icon=":material/add:",
                width="stretch",
                type="primary" if dispo > 0 else "secondary",
                disabled=dispo <= 0,
                on_click=_ajouter,
                args=(p.id,),
            )
    if len(produits) > nb:
        st.button(
            f"Afficher plus de produits ({len(produits) - nb})",
            key="vente_plus",
            width="stretch",
            on_click=lambda: st.session_state.__setitem__("vente_nb", nb + PAR_PAGE),
        )


# ------------------------------------------------------------------ Ticket
def _choix_mode(cle):
    """Gros boutons Espèces / Wave / Orange Money, et les autres moyens dans « Autre »."""
    choix = (
        st.segmented_control("Moyen de paiement", MODES_RAPIDES, default="Espèces", key=cle, width="stretch")
        or "Espèces"
    )
    if choix == "Autre":
        autres = [m for m in config.MODES_PAIEMENT if m not in MODES_RAPIDES]
        return st.selectbox("Autre moyen", autres, key=f"{cle}_autre")
    return choix


def _ticket(session):
    panier = _panier()
    with st.container(key="ticket_vente"):
        # Client
        st.markdown("<div class='tk-titre'>Client</div>", unsafe_allow_html=True)
        clients = session.query(Client).filter(Client.nom != CLIENT_PASSAGE).order_by(Client.nom).all()
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        with c1:
            client = config.choisir(
                "Client",
                clients,
                lambda c: f"{c.nom} · {c.telephone}",
                nouveau=CLIENT_PASSAGE,
                key="vente_client",
                label_visibility="collapsed",
            )
        with c2:
            _nouveau_client_rapide(session)
        encours = 0
        if client:
            encours = D.encours_client(session, client.id)
            retard = D.client_en_retard(session, client.id)
            nb_achats = session.query(func.count(Vente.id)).filter(Vente.client_id == client.id).scalar()
            st.markdown(ui.fiche_client_caisse(client, encours, retard, nb_achats), unsafe_allow_html=True)

        # Panier
        nb_articles = sum(panier.values())
        h, v = st.columns([3, 1.1], vertical_alignment="center")
        h.markdown(
            f"<div class='tk-titre'>Panier <span class='tk-nb'>{nb_articles} article{'s' if nb_articles > 1 else ''}"
            "</span></div>",
            unsafe_allow_html=True,
        )
        if panier:
            v.button(
                "Vider", key="vider_panier", type="tertiary", icon=":material/delete_sweep:", on_click=_vider_panier
            )
        else:
            st.markdown("<div class='tk-vide'>Panier vide</div>", unsafe_allow_html=True)
        sous_total = 0
        for pid in list(panier):
            p = session.get(Produit, pid)
            if p is None:
                panier.pop(pid)
                continue
            cle = f"q_{pid}"
            st.session_state.setdefault(cle, panier[pid])
            with st.container(key=f"tk_ligne_{pid}"):
                n1, n2 = st.columns([6, 0.5], vertical_alignment="center")
                n1.markdown(
                    f"<div class='tk-nom' title='{p.nom}'>{p.nom}</div>"
                    f"<div class='tk-pu'>{fmt_money(p.prix)} / {p.unite or 'pièce'}</div>",
                    unsafe_allow_html=True,
                )
                n2.button("", icon=":material/close:", key=f"del_{pid}", type="tertiary", help="Retirer",
                          on_click=_retirer, args=(pid,))  # fmt: skip
                m, q, pl, mt = st.columns([0.55, 1, 0.55, 1.9], vertical_alignment="center", gap="small")
                m.button("", icon=":material/remove:", key=f"tk_moins_{pid}", width="stretch", on_click=_changer,
                         args=(pid, -1, p.stock))  # fmt: skip
                qte = q.number_input(
                    "Qté", min_value=1, max_value=max(p.stock, 1), step=1, key=cle, label_visibility="collapsed"
                )
                pl.button("", icon=":material/add:", key=f"tk_plus_{pid}", width="stretch", on_click=_changer,
                          args=(pid, 1, p.stock), disabled=qte >= (p.stock or 0))  # fmt: skip
                panier[pid] = qte
                mt.markdown(f"<div class='tk-mt'>{fmt_money(p.prix * qte)}</div>", unsafe_allow_html=True)
            sous_total += p.prix * qte

        remise = 0
        if panier:
            r1, r2 = st.columns([2, 1.3], vertical_alignment="center")
            r1.markdown("<div class='tk-lib'>Remise (FCFA)</div>", unsafe_allow_html=True)
            remise = r2.number_input("Remise (FCFA)", min_value=0, max_value=int(sous_total), step=500, value=0,
                                     label_visibility="collapsed", key="vente_remise")  # fmt: skip
        total = max(sous_total - remise, 0)
        st.markdown(ui.totaux_caisse(sous_total, total), unsafe_allow_html=True)

        # Règlement
        st.markdown("<div class='tk-titre'>Règlement</div>", unsafe_allow_html=True)
        reglement = (
            st.segmented_control(
                "Règlement", [COMPTANT, DETTE], default=COMPTANT, key="reglement", label_visibility="collapsed",
                width="stretch",
            )
            or COMPTANT
        )  # fmt: skip
        credit = reglement == DETTE
        bloquant = None
        acompte, nb, frequence, date1, mode = 0, 1, "Mensuelle", None, "Espèces"

        if not credit:
            mode = _choix_mode("mode_comptant")
            if mode == "Espèces" and total:
                recu = st.number_input("Montant reçu", min_value=0, step=500, value=int(total), key="vente_recu")
                if recu > total:
                    st.success(f"Monnaie à rendre : **{fmt_money(recu - total)}**")
                elif recu < total:
                    st.warning(f"Il manque {fmt_money(total - recu)}.")
        else:
            if client is None:
                bloquant = "Choisissez le client pour une vente à crédit."
                st.warning(bloquant)
            acompte = st.number_input(
                "Avance versée aujourd'hui", min_value=0, max_value=max(int(total) - 1, 0), step=500, value=0
            )
            if acompte:
                mode = _choix_mode("mode_acompte")
            y1, y2 = st.columns(2)
            nb = y1.number_input("Payer en combien de fois ?", min_value=1, max_value=36, value=1)
            frequence = y2.selectbox("Tous les…", list(config.FREQUENCES), index=2)
            date1 = st.date_input(
                "Date du 1er paiement", value=D.ajouter_mois(date.today(), 1), min_value=date.today(),
                format="DD/MM/YYYY",
            )  # fmt: skip
            plan = D.generer_echeancier(total - acompte, nb, date1, frequence)
            if plan:
                st.markdown(
                    f"<div class='tk-ligne du'><span>Reste à payer</span><b>{fmt_money(total - acompte)}</b></div>"
                    + "".join(
                        f"<div class='tk-ech'><span>{fmt_date(d)}</span><span>{fmt_money(m)}</span></div>"
                        for d, m in plan
                    ),
                    unsafe_allow_html=True,
                )
            if client and client.plafond_credit and encours + total - acompte > client.plafond_credit:
                st.warning(f"Plafond de crédit dépassé ({fmt_money(client.plafond_credit)}).")
                if not st.checkbox("J'autorise quand même ce crédit"):
                    bloquant = "Plafond de crédit dépassé."

        # Validation
        if not panier:
            bloquant = bloquant or "Ajoutez au moins un produit."
        libelle = "Valider la vente à crédit" if credit else "Valider la vente"
        if st.button(libelle, type="primary", width="stretch", disabled=bool(bloquant), key="valider_vente",
                     icon=":material/check:"):  # fmt: skip
            _valider(session, client, panier, remise, total, credit, acompte, nb, frequence, date1, mode)


def _nouveau_client_rapide(session):
    with st.popover("", icon=":material/person_add:", help="Nouveau client", width="stretch"):
        with st.form("client_rapide", clear_on_submit=True):
            nom = st.text_input("Nom complet")
            tel = st.text_input("Téléphone", placeholder="77 123 45 67")
            if st.form_submit_button("Créer le client", type="primary"):
                if not nom or not tel:
                    st.error("Nom et téléphone obligatoires.")
                    return
                c = Client(nom=nom.strip(), telephone=tel.strip())
                session.add(c)
                session.commit()
                st.session_state["vente_client"] = c.id
                st.rerun()


def _valider(session, client, panier, remise, total, credit, acompte, nb, frequence, date1, mode):
    manquants = [p.nom for pid, q in panier.items() if (p := session.get(Produit, pid)).stock < q]
    if manquants:
        st.error("Stock insuffisant : " + ", ".join(manquants))
        return
    client = client or client_de_passage(session)
    try:
        vente = Vente(
            client_id=client.id,
            mode_livraison="Retrait en magasin",
            remise=remise,
            mode_paiement="Crédit" if credit else mode,
        )
        session.add(vente)
        session.flush()
        for pid, q in panier.items():
            p = session.get(Produit, pid)
            prix_vente = p.prix
            cout = sortie_stock(session, p, q, "Vente", f"Facture F-{vente.id:05d} · {client.nom}")
            session.add(VenteProduit(vente_id=vente.id, produit_id=pid, quantite=q, prix_unit=prix_vente, cout=cout))
            session.add(
                HistoriqueVente(
                    vente_id=vente.id,
                    client_nom=client.nom,
                    client_telephone=client.telephone,
                    produit_nom=p.nom,
                    quantite=q,
                    prix_unit=prix_vente,
                    date=datetime.now(),
                )
            )
        if credit:
            D.creer_dette(
                session,
                client.id,
                total,
                nb_versements=nb,
                date_premiere=date1,
                frequence=frequence,
                acompte=acompte,
                mode_acompte=mode,
                vente_id=vente.id,
                description=f"Achat facture F-{vente.id:05d}",
            )
        else:
            session.add(
                Paiement(client_id=client.id, vente_id=vente.id, montant=total, mode=mode, note="Paiement comptant")
            )
        session.commit()
    except (D.ErreurDette, ErreurStock) as e:
        session.rollback()
        st.error(str(e))
        return
    _vider_panier()
    st.session_state["derniere_vente"] = vente.id
    st.rerun()


# ------------------------------------------------------------------ Confirmation + documents
def _confirmation(session, vente_id):
    vente = session.get(Vente, vente_id)
    if vente is None:
        st.session_state.pop("derniere_vente")
        st.rerun()
    params = get_params()
    d = vente.dette
    config.entete("Vente enregistrée", f"Facture F-{vente.id:05d}, {vente.client.nom}, {fmt_money(vente.total)}")
    if d:
        config.kpis(
            [
                ("Total de la vente", fmt_money(vente.total), config.SECONDARY_BLUE, ""),
                ("Avance reçue", fmt_money(d.total_paye), config.SUCCESS_GREEN, ""),
                (
                    "Reste à payer (dette)",
                    fmt_money(d.reste),
                    config.WARNING_ORANGE,
                    f"dernier paiement le {fmt_date(d.date_echeance_finale)}",
                ),
            ]
        )
    else:
        st.success(f"Payé comptant ({vente.mode_paiement}) : {fmt_money(vente.total)}")

    apercu, docs = st.columns([1, 1.3], gap="large")
    apercu.markdown(ui.ticket_recu(vente, params["boutique_nom"], d), unsafe_allow_html=True)
    docs.markdown("##### Documents à imprimer ou envoyer")
    cols = [docs, docs, docs]
    cols[0].download_button(
        "Facture",
        documents.facture(vente, params),
        f"Facture_F-{vente.id:05d}.pdf",
        "application/pdf",
        width="stretch",
    )
    if d:
        cols[1].download_button(
            "Reconnaissance de dette",
            documents.reconnaissance_dette(d, params),
            f"Reconnaissance_dette_D-{d.id:05d}.pdf",
            "application/pdf",
            width="stretch",
            type="primary",
        )
        if d.paiements:
            p = d.paiements[0]
            cols[2].download_button(
                "Reçu de l'avance",
                documents.recu(p, params),
                f"Recu_R-{p.id:05d}.pdf",
                "application/pdf",
                width="stretch",
            )
    st.divider()
    b1, b2, _ = st.columns([1, 1, 2])
    b1.button(  # callback : un seul chargement
        "Nouvelle vente",
        type="primary",
        width="stretch",
        on_click=lambda: st.session_state.pop("derniere_vente", None),
    )
    if d:
        config.bouton_page(
            b2,
            "Voir la dette",
            "Dettes",
            etat={"dette_ouverte": d.id, "derniere_vente": None},
            width="stretch",
        )
