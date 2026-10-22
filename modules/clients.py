"""Clients : liste, fiche client (achats, dettes, versements), relevé de compte."""

import pandas as pd
import streamlit as st

import config
from config import fmt_date, fmt_money
from db import dettes as D
from db.models import Client, get_session
from db.utils import get_params
from modules import documents


def show_clients():
    with get_session() as session:
        config.entete("Clients", "Vos clients, ce qu'ils ont acheté et ce qu'ils vous doivent.")
        a, b = st.columns([1, 4], vertical_alignment="bottom")
        if a.button("➕ Nouveau client", type="primary", use_container_width=True):
            _dialog_client(None)
        recherche = b.text_input(
            "Rechercher", placeholder="🔎  Nom, téléphone, quartier…", label_visibility="collapsed"
        )

        clients = session.query(Client).filter(Client.nom != config.CLIENT_PASSAGE).order_by(Client.nom).all()
        if recherche:
            r = recherche.lower()
            clients = [c for c in clients if r in f"{c.nom} {c.telephone} {c.adresse or ''}".lower()]
        if not clients:
            st.info("Aucun client. Cliquez sur **➕ Nouveau client**.")
            return

        lignes = []
        for c in clients:
            encours = D.encours_client(session, c.id)
            retard = D.client_en_retard(session, c.id)
            lignes.append(
                {
                    "Client": c.nom,
                    "Téléphone": c.telephone,
                    "Quartier": c.adresse or "",
                    "Achats": len(c.ventes),
                    "Total acheté": sum(v.total for v in c.ventes),
                    "Doit": encours,
                    "Situation": "🔴 En retard" if retard else ("🟠 Dette en cours" if encours else "🟢 À jour"),
                }
            )
        df = pd.DataFrame(lignes)
        st.caption(f"{len(df)} client(s) · 👆 Cliquez sur un client pour ouvrir sa fiche.")
        event = st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="table_clients",
            column_config={k: st.column_config.NumberColumn(format="localized") for k in ["Total acheté", "Doit"]},
        )
        if event.selection.rows:
            st.session_state["client_ouvert"] = clients[event.selection.rows[0]].id
        ouvert = st.session_state.get("client_ouvert")
        if ouvert in {c.id for c in clients}:
            st.divider()
            _fiche(session, session.get(Client, ouvert))


def _fiche(session, c):
    params = get_params()
    encours = D.encours_client(session, c.id)
    st.markdown(
        f"### {c.nom}  \n<small>📞 {c.telephone or '—'} · {c.adresse or ''} · client depuis le "
        f"{fmt_date(c.date_creation)}</small>",
        unsafe_allow_html=True,
    )
    config.kpis(
        [
            (
                "Total acheté",
                fmt_money(sum(v.total for v in c.ventes)),
                config.SECONDARY_BLUE,
                f"{len(c.ventes)} achat(s)",
            ),
            ("Doit actuellement", fmt_money(encours), config.DANGER_RED if encours else config.SUCCESS_GREEN, ""),
            ("Plafond de crédit", fmt_money(c.plafond_credit) if c.plafond_credit else "Aucun", config.MUTED, ""),
        ]
    )
    st.write("")
    b = st.columns(4)
    if b[0].button("🛒 Lui vendre", type="primary", use_container_width=True):
        config.aller_a("Ventes", vente_client=c.id)
    if b[1].button("✏️ Modifier", use_container_width=True):
        _dialog_client(c.id)
    b[2].download_button(
        "📄 Relevé de compte",
        documents.releve_client(c, params),
        f"Releve_{c.nom}.pdf",
        "application/pdf",
        use_container_width=True,
    )
    if encours and b[3].button("💳 Voir ses dettes", use_container_width=True):
        actives = [d for d in c.dettes if d.statut == "en_cours"]
        config.aller_a("Dettes", dette_ouverte=actives[0].id if actives else None)

    t1, t2, t3 = st.tabs(["Achats", "Dettes", "Versements"])
    with t1:
        if c.ventes:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Facture": f"F-{v.id:05d}",
                            "Date": v.date.strftime("%d/%m/%Y"),
                            "Produits": ", ".join(
                                f"{vp.quantite}× {vp.produit.nom}" for vp in v.produits if vp.produit
                            ),
                            "Total": v.total,
                            "Règlement": "Crédit" if v.dette else v.mode_paiement,
                        }
                        for v in sorted(c.ventes, key=lambda v: v.date, reverse=True)
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={"Total": st.column_config.NumberColumn(format="localized")},
            )
        else:
            st.caption("Aucun achat.")
    with t2:
        if c.dettes:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Dette": f"D-{d.id:05d}",
                            "Date": fmt_date(d.date_creation),
                            "Objet": d.description,
                            "Montant": d.montant,
                            "Versé": d.total_paye,
                            "Reste": d.reste,
                            "Statut": D.situation_dette(d)["statut"],
                        }
                        for d in c.dettes
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={
                    k: st.column_config.NumberColumn(format="localized") for k in ["Montant", "Versé", "Reste"]
                },
            )
        else:
            st.caption("Aucune dette.")
    with t3:
        pay = sorted((p for d in c.dettes for p in d.paiements), key=lambda p: p.date, reverse=True)
        if pay:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Reçu": f"R-{p.id:05d}",
                            "Date": p.date.strftime("%d/%m/%Y"),
                            "Montant": p.montant,
                            "Moyen": p.mode,
                        }
                        for p in pay
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={"Montant": st.column_config.NumberColumn(format="localized")},
            )
        else:
            st.caption("Aucun versement sur dette.")
    if c.notes:
        st.caption(f"📝 {c.notes}")


@st.dialog("Client")
def _dialog_client(client_id):
    with get_session() as session:
        c = session.get(Client, client_id) if client_id else None
        with st.form("form_client"):
            nom = st.text_input("Nom complet *", value=c.nom if c else "")
            tel = st.text_input("Téléphone *", value=c.telephone if c else "", placeholder="77 123 45 67")
            adresse = st.text_input("Quartier / adresse", value=(c.adresse or "") if c else "")
            email = st.text_input("Email", value=(c.email or "") if c else "")
            plafond = st.number_input(
                "Plafond de crédit (0 = sans limite)",
                min_value=0,
                step=5000,
                value=int(c.plafond_credit or 0) if c else 0,
                help="Montant maximum que ce client peut devoir",
            )
            notes = st.text_area("Notes", value=(c.notes or "") if c else "", height=70)
            if st.form_submit_button("Enregistrer", type="primary", use_container_width=True):
                if not nom.strip() or not tel.strip():
                    st.error("Le nom et le téléphone sont obligatoires.")
                    return
                doublon = session.query(Client).filter_by(telephone=tel.strip()).first()
                if doublon and (c is None or doublon.id != c.id):
                    st.error(f"Ce numéro appartient déjà à {doublon.nom}.")
                    return
                if c is None:
                    c = Client()
                    session.add(c)
                c.nom, c.telephone, c.adresse, c.email = nom.strip(), tel.strip(), adresse, email
                c.plafond_credit, c.notes = plafond, notes
                session.commit()
                st.session_state["client_ouvert"] = c.id
                config.flash(f"Client {c.nom} enregistré.")
                st.rerun()
        if c is not None and not c.ventes and not c.dettes:
            if st.button("🗑️ Supprimer ce client"):
                session.delete(c)
                session.commit()
                st.session_state.pop("client_ouvert", None)
                st.rerun()
