from datetime import date, datetime

import pandas as pd
import streamlit as st

import config
from config import fmt_date, fmt_money
from db import dettes as D
from db.models import Client, HistoriqueVente, Paiement, Produit, Vente, VenteProduit, get_session


def _panier():
    # {produit_id: quantite} — on stocke des IDs, jamais des objets SQLAlchemy
    return st.session_state.setdefault("panier", {})


def show_ventes():
    st.markdown("<h2 style='color: #1e3a8a;'>🛒 Nouvelle vente</h2>", unsafe_allow_html=True)
    with get_session() as session:
        _page(session)


def _page(session):
    clients = session.query(Client).order_by(Client.nom).all()
    if not clients:
        st.warning("⚠️ Ajoutez d'abord des clients pour effectuer des ventes")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Client")
        client = config.choisir("Choisir un client", clients, lambda c: f"{c.nom} ({c.telephone})", key="vente_client")
        encours = D.encours_client(session, client.id)
        en_retard = D.client_en_retard(session, client.id)
        st.markdown(
            f"""
            <div style='background-color:#dbeafe;padding:1rem;border-radius:8px;margin-top:0.5rem;'>
                <p style='margin:0'><strong>{client.nom}</strong> — {client.telephone}</p>
                <p style='margin:4px 0 0 0'>Dette en cours : <strong>{fmt_money(encours)}</strong>
                {" · Plafond : " + fmt_money(client.plafond_credit) if client.plafond_credit else ""}</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        if en_retard:
            st.error("⛔ Ce client a une dette EN RETARD. Pensez à la relancer avant de lui faire crédit.")

    with col2:
        st.markdown("### Livraison")
        mode_livraison = st.radio(
            "Mode de livraison",
            ["Retrait en magasin", "Livraison à domicile"],
            horizontal=True,
            label_visibility="collapsed",
        )
        st.markdown("### Recherche produit")
        recherche = st.text_input("Nom du produit", placeholder="Ex : riz, huile, téléphone…")

    panier = _panier()

    if recherche:
        trouves = session.query(Produit).filter(Produit.nom.ilike(f"%{recherche}%"), Produit.stock > 0).all()
        if not trouves:
            st.info("Aucun produit en stock ne correspond.")
        cols = st.columns(3)
        for i, p in enumerate(trouves):
            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div style='border:1px solid #e2e8f0;padding:0.8rem;border-radius:8px;
                                margin-bottom:0.5rem;background:white'>
                        <h4 style='margin:0;color:#1e3a8a;'>{p.nom}</h4>
                        <p style='margin:4px 0 0 0;'>{fmt_money(p.prix)} · Stock : {p.stock}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )
                qty = st.number_input("Quantité", min_value=1, max_value=p.stock, step=1, key=f"qty_{p.id}")
                if st.button("➕ Ajouter", key=f"add_{p.id}"):
                    panier[p.id] = min(panier.get(p.id, 0) + qty, p.stock)
                    st.session_state.pop("editeur_panier", None)
                    st.rerun()

    if not panier:
        return

    st.markdown("---")
    st.markdown("### 🛍️ Panier")
    lignes, sous_total = [], 0
    for pid, qty in list(panier.items()):
        p = session.get(Produit, pid)
        if p is None:
            panier.pop(pid)
            continue
        sous_total += p.prix * qty
        lignes.append(
            {
                "ID": pid,
                "Produit": p.nom,
                "Prix unitaire": p.prix,
                "Quantité": qty,
                "Stock dispo": p.stock,
                "Total": p.prix * qty,
            }
        )
    df = pd.DataFrame(lignes)
    edite = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        key="editeur_panier",
        disabled=["ID", "Produit", "Prix unitaire", "Stock dispo", "Total"],
        column_config={
            "ID": None,
            "Quantité": st.column_config.NumberColumn(min_value=0, step=1, help="Mettre 0 pour retirer le produit"),
            "Prix unitaire": st.column_config.NumberColumn(format="%d"),
            "Total": st.column_config.NumberColumn(format="%d"),
        },
    )
    changements = {
        int(r.ID): int(r["Quantité"]) for _, r in edite.iterrows() if int(r["Quantité"]) != panier.get(int(r.ID))
    }
    if changements:
        for pid, q in changements.items():
            if q <= 0:
                panier.pop(pid, None)
            else:
                panier[pid] = q
        st.session_state.pop("editeur_panier", None)
        st.rerun()

    # ---------- Paiement ----------
    st.markdown("### 💳 Paiement")
    c1, c2, c3 = st.columns(3)
    with c1:
        remise = st.number_input("Remise (FCFA)", min_value=0, max_value=int(sous_total), step=500, value=0)
    total = max(sous_total - remise, 0)
    with c2:
        type_paiement = st.radio("Type de paiement", ["Comptant", "À crédit (dette)"], horizontal=True)
    with c3:
        mode_paiement = st.selectbox("Moyen de paiement", config.MODES_PAIEMENT)

    credit = type_paiement != "Comptant"
    acompte, nb_versements, frequence, date_premiere = 0, 1, "Mensuelle", None
    if credit:
        st.markdown("#### 📅 Conditions de la dette")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            acompte = st.number_input(
                "Acompte versé aujourd'hui", min_value=0, max_value=max(int(total) - 1, 0), step=500, value=0
            )
        with d2:
            nb_versements = st.number_input("Nombre de versements", min_value=1, max_value=36, value=1)
        with d3:
            frequence = st.selectbox("Fréquence", list(config.FREQUENCES))
        with d4:
            date_premiere = st.date_input(
                "1ère échéance", value=D.ajouter_mois(date.today(), 1), min_value=date.today(), format="DD/MM/YYYY"
            )
        plan = D.generer_echeancier(total - acompte, nb_versements, date_premiere, frequence)
        if plan:
            st.caption("Échéancier prévu : " + " · ".join(f"{fmt_date(d)} → {fmt_money(m)}" for d, m in plan))

        nouvel_encours = encours + total - acompte
        if client.plafond_credit and nouvel_encours > client.plafond_credit:
            st.warning(
                f"⚠️ Avec cette vente, la dette du client passerait à {fmt_money(nouvel_encours)}, "
                f"au-dessus de son plafond de {fmt_money(client.plafond_credit)}."
            )
            forcer = st.checkbox("Autoriser quand même ce crédit")
        else:
            forcer = True
    else:
        forcer = True

    recap = f"Total : {fmt_money(total)}"
    if credit:
        recap += (
            f" &nbsp;·&nbsp; Payé aujourd'hui : {fmt_money(acompte)}"
            f" &nbsp;·&nbsp; Reste dû : {fmt_money(total - acompte)}"
        )
    st.markdown(
        f"""
        <div style='background-color:#1e3a8a;color:white;padding:1rem;border-radius:8px;margin:1rem 0;'>
            <h3 style='margin:0;color:white;'>{recap}</h3>
        </div>""",
        unsafe_allow_html=True,
    )

    b1, b2, b3 = st.columns(3)
    with b2:
        valider = st.button("✅ Valider la vente", use_container_width=True, disabled=not forcer or total <= 0)
    with b3:
        if st.button("🗑️ Vider le panier", use_container_width=True):
            st.session_state["panier"] = {}
            st.rerun()

    if valider:
        # Vérification du stock au moment de valider (il a pu changer)
        manquants = [session.get(Produit, pid).nom for pid, q in panier.items() if session.get(Produit, pid).stock < q]
        if manquants:
            st.error("Stock insuffisant pour : " + ", ".join(manquants))
            return
        try:
            vente = Vente(
                client_id=client.id,
                mode_livraison=mode_livraison,
                remise=remise,
                mode_paiement="Crédit" if credit else mode_paiement,
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
                    nb_versements=nb_versements,
                    date_premiere=date_premiere,
                    frequence=frequence,
                    acompte=acompte,
                    mode_acompte=mode_paiement,
                    vente_id=vente.id,
                    description=f"Vente F-{vente.id:05d}",
                )
            else:
                session.add(
                    Paiement(
                        client_id=client.id,
                        vente_id=vente.id,
                        montant=total,
                        mode=mode_paiement,
                        note="Paiement comptant",
                    )
                )
            session.commit()
        except D.ErreurDette as e:
            session.rollback()
            st.error(str(e))
            return
        st.session_state["panier"] = {}
        st.session_state["flash"] = f"✅ Vente F-{vente.id:05d} enregistrée" + (
            " — dette créée, visible dans 💳 Dettes." if credit else "."
        )
        st.rerun()
