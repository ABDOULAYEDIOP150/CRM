"""Caisse : nouvelle vente en 4 étapes, avec le choix Comptant / Dette toujours visible."""

from datetime import date, datetime

import streamlit as st

import config
from config import CLIENT_PASSAGE, fmt_date, fmt_money
from db import dettes as D
from db.models import Client, HistoriqueVente, Paiement, Produit, Vente, VenteProduit, get_session
from db.utils import client_de_passage, get_params
from modules import documents

COMPTANT = "💵 Payé comptant"
DETTE = "📝 À crédit (dette)"


def _panier():
    return st.session_state.setdefault("panier", {})  # {produit_id: quantité}


def _vider_panier():
    for cle in [k for k in st.session_state if str(k).startswith("q_")]:
        del st.session_state[cle]
    st.session_state["panier"] = {}


def show_ventes():
    with get_session() as session:
        if st.session_state.get("derniere_vente"):
            _confirmation(session, st.session_state["derniere_vente"])
            return
        config.entete(
            "Nouvelle vente", "① Ajoutez les produits  ·  ② Choisissez le client  ·  ③ Comptant ou dette  ·  ④ Validez"
        )
        gauche, droite = st.columns([3, 2], gap="large")
        with gauche:
            _catalogue(session)
        with droite:
            _ticket(session)


# ------------------------------------------------------------------ ① Catalogue
def _catalogue(session):
    panier = _panier()
    st.markdown("##### ① Produits")
    recherche = st.text_input(
        "Rechercher un produit", placeholder="🔎  Riz, huile, savon…", label_visibility="collapsed"
    )
    q = session.query(Produit).order_by(Produit.nom)
    if recherche:
        q = q.filter(Produit.nom.ilike(f"%{recherche}%"))
    produits = q.all()
    if not produits:
        st.info("Aucun produit. Ajoutez vos produits dans **Produits & stock**.")
        if st.button("📦 Ajouter des produits"):
            config.aller_a("Produits")
        return
    cols = st.columns(3)
    for i, p in enumerate(produits):
        dans_panier = panier.get(p.id, 0)
        dispo = p.stock - dans_panier
        with cols[i % 3].container(border=True):
            st.markdown(
                f"<div class='crm-prod'>{p.nom}</div><div class='crm-prix'>{fmt_money(p.prix)}</div>"
                f"<div class='crm-stock'>{'Rupture de stock' if p.stock <= 0 else f'Stock : {p.stock}'}"
                f"{f' · {dans_panier} au panier' if dans_panier else ''}</div>",
                unsafe_allow_html=True,
            )
            if st.button("➕ Ajouter", key=f"add_{p.id}", use_container_width=True, disabled=dispo <= 0):
                panier[p.id] = dans_panier + 1
                st.session_state[f"q_{p.id}"] = panier[p.id]


# ------------------------------------------------------------------ ②③④ Ticket
def _ticket(session):
    panier = _panier()
    with st.container(border=True):
        # ② Client
        st.markdown("##### ② Client")
        clients = session.query(Client).filter(Client.nom != CLIENT_PASSAGE).order_by(Client.nom).all()
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
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
            if D.client_en_retard(session, client.id):
                st.error(f"⚠️ {client.nom} a une dette **en retard** ({fmt_money(encours)} dû au total).")
            elif encours:
                st.caption(f"Dette en cours : **{fmt_money(encours)}**")

        # Lignes du panier
        st.markdown("##### 🧾 Panier")
        if not panier:
            st.info("Le panier est vide : cliquez sur **➕ Ajouter** à gauche.")
        sous_total = 0
        for pid in list(panier):
            p = session.get(Produit, pid)
            if p is None:
                panier.pop(pid)
                continue
            cle = f"q_{pid}"
            st.session_state.setdefault(cle, panier[pid])
            a, b, c = st.columns([5, 2, 1], vertical_alignment="center")
            qte = b.number_input(
                "Qté", min_value=1, max_value=max(p.stock, 1), step=1, key=cle, label_visibility="collapsed"
            )
            panier[pid] = qte
            a.markdown(
                f"**{p.nom}**  \n<small>{fmt_money(p.prix)} × {qte} = <b>{fmt_money(p.prix * qte)}</b></small>",
                unsafe_allow_html=True,
            )
            if c.button("", icon=":material/delete:", key=f"del_{pid}", help="Retirer du panier"):
                panier.pop(pid)
                del st.session_state[cle]
                st.rerun()
            sous_total += p.prix * qte

        remise = 0
        if panier:
            remise = st.number_input("Remise (FCFA)", min_value=0, max_value=int(sous_total), step=500, value=0)
        total = max(sous_total - remise, 0)
        st.markdown(f"<div class='crm-total'><span>TOTAL</span><b>{fmt_money(total)}</b></div>", unsafe_allow_html=True)

        # ③ Règlement — toujours visible
        st.markdown("##### ③ Règlement")
        reglement = (
            st.segmented_control(
                "Règlement", [COMPTANT, DETTE], default=COMPTANT, key="reglement", label_visibility="collapsed"
            )
            or COMPTANT
        )
        credit = reglement == DETTE
        bloquant = None
        acompte, nb, frequence, date1, mode = 0, 1, "Mensuelle", None, "Espèces"

        if not credit:
            mode = st.selectbox("Moyen de paiement", config.MODES_PAIEMENT, key="mode_comptant")
            if mode == "Espèces" and total:
                recu = st.number_input(
                    "Montant reçu du client (pour calculer la monnaie)", min_value=0, step=500, value=int(total)
                )
                if recu > total:
                    st.success(f"Monnaie à rendre : **{fmt_money(recu - total)}**")
                elif recu < total:
                    st.warning(
                        f"Il manque {fmt_money(total - recu)}. Choisissez « À crédit » si le client paie plus tard."
                    )
        else:
            if client is None:
                bloquant = "Pour une dette, choisissez le client (ou créez-le avec ➕)."
                st.warning("👤 " + bloquant)
            x1, x2 = st.columns(2)
            acompte = x1.number_input(
                "Avance versée aujourd'hui",
                min_value=0,
                max_value=max(int(total) - 1, 0),
                step=500,
                value=0,
                help="Ce que le client donne maintenant (0 si rien)",
            )
            mode = x2.selectbox("Moyen de l'avance", config.MODES_PAIEMENT, key="mode_acompte")
            y1, y2 = st.columns(2)
            nb = y1.number_input("Payer en combien de fois ?", min_value=1, max_value=36, value=1)
            frequence = y2.selectbox("Tous les…", list(config.FREQUENCES), index=2)
            date1 = st.date_input(
                "Date du 1er paiement",
                value=D.ajouter_mois(date.today(), 1),
                min_value=date.today(),
                format="DD/MM/YYYY",
            )
            plan = D.generer_echeancier(total - acompte, nb, date1, frequence)
            if plan:
                st.markdown(
                    f"Reste à payer : **{fmt_money(total - acompte)}**  \n"
                    + "  \n".join(f"• {fmt_date(d)} : {fmt_money(m)}" for d, m in plan)
                )
            if client and client.plafond_credit and encours + total - acompte > client.plafond_credit:
                st.warning(f"Plafond de crédit dépassé ({fmt_money(client.plafond_credit)}).")
                if not st.checkbox("J'autorise quand même ce crédit"):
                    bloquant = "Plafond de crédit dépassé."

        # ④ Validation
        if not panier:
            bloquant = bloquant or "Ajoutez au moins un produit."
        libelle = "✅ Valider la vente à crédit" if credit else "✅ Valider la vente"
        if st.button(libelle, type="primary", use_container_width=True, disabled=bool(bloquant)):
            _valider(session, client, panier, remise, total, credit, acompte, nb, frequence, date1, mode)


def _nouveau_client_rapide(session):
    with st.popover("➕", help="Nouveau client", use_container_width=True):
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
            session.add(VenteProduit(vente_id=vente.id, produit_id=pid, quantite=q, prix_unit=p.prix))
            p.stock -= q
            session.add(
                HistoriqueVente(
                    vente_id=vente.id,
                    client_nom=client.nom,
                    client_telephone=client.telephone,
                    produit_nom=p.nom,
                    quantite=q,
                    prix_unit=p.prix,
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
    except D.ErreurDette as e:
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
    config.entete("Vente enregistrée ✅", f"Facture F-{vente.id:05d} · {vente.client.nom} · {fmt_money(vente.total)}")
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
        st.info("📝 Faites signer la **reconnaissance de dette** au client et gardez un exemplaire.")
    else:
        st.success(f"Payé comptant ({vente.mode_paiement}) : {fmt_money(vente.total)}")

    st.markdown("##### Documents à imprimer / envoyer")
    cols = st.columns(3)
    cols[0].download_button(
        "📄 Facture",
        documents.facture(vente, params),
        f"Facture_F-{vente.id:05d}.pdf",
        "application/pdf",
        use_container_width=True,
    )
    if d:
        cols[1].download_button(
            "✍️ Reconnaissance de dette",
            documents.reconnaissance_dette(d, params),
            f"Reconnaissance_dette_D-{d.id:05d}.pdf",
            "application/pdf",
            use_container_width=True,
            type="primary",
        )
        if d.paiements:
            p = d.paiements[0]
            cols[2].download_button(
                "🧾 Reçu de l'avance",
                documents.recu(p, params),
                f"Recu_R-{p.id:05d}.pdf",
                "application/pdf",
                use_container_width=True,
            )
    st.divider()
    b1, b2, _ = st.columns([1, 1, 2])
    if b1.button("🛒 Nouvelle vente", type="primary", use_container_width=True):
        st.session_state.pop("derniere_vente")
        st.rerun()
    if d and b2.button("💳 Voir la dette", use_container_width=True):
        st.session_state.pop("derniere_vente")
        config.aller_a("Dettes", dette_ouverte=d.id)
