"""Dettes clients : qui doit combien, jusqu'à quand ; encaisser, imprimer, relancer."""

from datetime import date

import pandas as pd
import streamlit as st

import config
from config import fmt_date, fmt_money
from db import dettes as D
from db.models import Client, Dette, Paiement, get_session
from db.utils import get_params
from modules import documents

COULEURS = {
    D.STATUT_RETARD: config.DANGER_RED,
    D.STATUT_A_JOUR: config.SECONDARY_BLUE,
    D.STATUT_SOLDEE: config.SUCCESS_GREEN,
    D.STATUT_ANNULEE: config.MUTED,
}
ICONES = {D.STATUT_RETARD: "🔴", D.STATUT_A_JOUR: "🟢", D.STATUT_SOLDEE: "✅", D.STATUT_ANNULEE: "⚪"}
VUES = ["À encaisser", "En retard", "Soldées", "Tous les versements"]


def show_dettes():
    params = get_params()
    with get_session() as session:
        config.entete("Dettes clients", "Qui vous doit de l'argent, combien, et jusqu'à quand.")
        r = D.resume_creances(session, jours_alerte=int(params["jours_alerte_echeance"]))
        config.kpis(
            [
                (
                    "Total à encaisser",
                    fmt_money(r["total_du"]),
                    config.SECONDARY_BLUE,
                    f"{r['nb_debiteurs']} client(s)",
                ),
                ("En retard", fmt_money(r["montant_retard"]), config.DANGER_RED, f"{len(r['retards'])} dette(s)"),
                (
                    "Échéances proches",
                    len(r["echeances_proches"]),
                    config.WARNING_ORANGE,
                    f"dans les {params['jours_alerte_echeance']} jours",
                ),
                ("Encaissé ce mois", fmt_money(_encaisse_mois(session)), config.SUCCESS_GREEN, "versements reçus"),
            ]
        )
        st.write("")
        a, b, _ = st.columns([1.3, 1.3, 3])
        if a.button(
            "➕ Nouvelle dette",
            type="primary",
            use_container_width=True,
            help="Dette sans vente : ancienne dette du cahier, argent prêté…",
        ):
            _dialog_nouvelle_dette()
        if b.button("🛒 Vente à crédit", use_container_width=True):
            config.aller_a("Ventes")

        vue = st.segmented_control("Vue", VUES, default=VUES[0], key="vue_dettes", label_visibility="collapsed")
        vue = vue or VUES[0]
        if vue == "Tous les versements":
            _versements(session, params)
            return
        _liste(session, params, vue)


def _encaisse_mois(session):
    debut, fin = config.get_date_range("Ce mois")
    return sum(
        p.montant
        for p in session.query(Paiement).filter(Paiement.dette_id.isnot(None), Paiement.date.between(debut, fin))
    )


# ------------------------------------------------------------------ Liste + détail
def _liste(session, params, vue):
    lignes = []
    for d in session.query(Dette).all():
        s = D.situation_dette(d)
        if vue == "À encaisser" and s["statut"] not in (D.STATUT_RETARD, D.STATUT_A_JOUR):
            continue
        if vue == "En retard" and s["statut"] != D.STATUT_RETARD:
            continue
        if vue == "Soldées" and s["statut"] != D.STATUT_SOLDEE:
            continue
        lignes.append((d, s))
    recherche = st.text_input("Rechercher", placeholder="🔎  Nom ou téléphone du client", label_visibility="collapsed")
    if recherche:
        lignes = [(d, s) for d, s in lignes if recherche.lower() in f"{d.client.nom} {d.client.telephone}".lower()]
    if not lignes:
        st.info("Aucune dette ici. 👍")
        return
    lignes.sort(
        key=lambda x: (x[1]["statut"] != D.STATUT_RETARD, -x[1]["jours_retard"], x[1]["prochaine_date"] or date.max)
    )

    df = pd.DataFrame(
        [
            {
                "Client": d.client.nom,
                "Téléphone": d.client.telephone,
                "Objet": d.description or "—",
                "Montant": d.montant,
                "Versé": d.total_paye,
                "Reste": d.reste,
                "Prochain paiement": fmt_date(s["prochaine_date"]) if d.reste else "—",
                "Statut": f"{ICONES[s['statut']]} {s['statut']}"
                + (f" ({s['jours_retard']} j)" if s["jours_retard"] else ""),
            }
            for d, s in lignes
        ]
    )
    st.caption("👆 Cliquez sur une ligne pour ouvrir la dette, encaisser un versement ou imprimer les documents.")
    event = st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"table_dettes_{vue}",
        column_config={c: st.column_config.NumberColumn(format="localized") for c in ["Montant", "Versé", "Reste"]},
    )
    ids = [d.id for d, _ in lignes]
    if event.selection.rows:
        st.session_state["dette_ouverte"] = ids[event.selection.rows[0]]
    ouverte = st.session_state.get("dette_ouverte")
    if ouverte in ids:
        st.divider()
        _detail(session, session.get(Dette, ouverte), params)


def _detail(session, dette, params):
    s = D.situation_dette(dette)
    c = dette.client
    st.markdown(
        f"### {c.nom} &nbsp; {config.badge(s['statut'], COULEURS[s['statut']])}  \n"
        f"<small>📞 {c.telephone or '—'} · {dette.description or ''} · dette D-{dette.id:05d} du "
        f"{fmt_date(dette.date_creation)}</small>",
        unsafe_allow_html=True,
    )
    config.kpis(
        [
            ("Montant", fmt_money(dette.montant), config.SECONDARY_BLUE, ""),
            (
                "Déjà versé",
                fmt_money(dette.total_paye),
                config.SUCCESS_GREEN,
                f"{dette.total_paye / dette.montant:.0%}" if dette.montant else "",
            ),
            (
                "Reste à payer",
                fmt_money(dette.reste),
                COULEURS[s["statut"]],
                f"{fmt_money(s['montant_retard'])} en retard" if s["montant_retard"] else "",
            ),
            (
                "Prochain paiement",
                fmt_date(s["prochaine_date"]) if dette.reste else "—",
                config.WARNING_ORANGE,
                fmt_money(s["prochain_montant"]) if dette.reste else "",
            ),
        ]
    )
    st.write("")

    actif = dette.statut == "en_cours" and dette.reste > 0
    b = st.columns(4)
    if actif and b[0].button("💰 Encaisser un versement", type="primary", use_container_width=True):
        _dialog_versement(dette.id)
    b[1].download_button(
        "✍️ Reconnaissance de dette",
        documents.reconnaissance_dette(dette, params),
        f"Reconnaissance_dette_D-{dette.id:05d}.pdf",
        "application/pdf",
        use_container_width=True,
    )
    b[2].download_button(
        "📄 Relevé du client",
        documents.releve_client(c, params),
        f"Releve_{c.nom}.pdf",
        "application/pdf",
        use_container_width=True,
    )
    if actif:
        msg = D.message_relance(
            params["message_relance"],
            c,
            dette.reste,
            s["prochaine_date"],
            params["boutique_nom"],
            params["boutique_telephone"],
            fmt_money,
        )
        lien = D.lien_whatsapp(c.telephone, msg)
        if lien:
            b[3].link_button("📲 Relancer (WhatsApp)", lien, use_container_width=True)

    g, dr = st.columns([3, 2], gap="large")
    with g:
        st.markdown("##### 📅 Échéancier")
        ech = D.etat_echeances(dette)
        if ech:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "N°": l["numero"],
                            "Date": fmt_date(l["date"]),
                            "Prévu": l["montant"],
                            "Versé": l["couvert"],
                            "Reste": l["reste"],
                            "Statut": l["statut"] + (f" ({l['jours_retard']} j)" if l["jours_retard"] else ""),
                        }
                        for l in ech
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={
                    k: st.column_config.NumberColumn(format="localized") for k in ["Prévu", "Versé", "Reste"]
                },
            )
        else:
            st.caption("Pas d'échéancier.")
    with dr:
        st.markdown("##### 🧾 Versements reçus")
        if not dette.paiements:
            st.caption("Aucun versement pour l'instant.")
        for p in reversed(dette.paiements):
            x, y = st.columns([3, 1], vertical_alignment="center")
            x.markdown(
                f"**{fmt_money(p.montant)}** · {p.mode}  \n<small>{p.date.strftime('%d/%m/%Y %H:%M')}"
                f"{' · ' + p.note if p.note else ''}</small>",
                unsafe_allow_html=True,
            )
            y.download_button(
                "Reçu",
                documents.recu(p, params),
                f"Recu_R-{p.id:05d}.pdf",
                "application/pdf",
                key=f"recu_{p.id}",
                use_container_width=True,
            )

    if actif:
        with st.expander("Autres actions : donner plus de temps, annuler"):
            with st.form(f"reech_{dette.id}"):
                st.markdown("**🔁 Donner plus de temps** (recalcule l'échéancier sur ce qui reste à payer)")
                k1, k2, k3 = st.columns(3)
                nb = k1.number_input("Nombre de paiements", 1, 36, 2)
                freq = k2.selectbox("Tous les…", list(config.FREQUENCES), index=2)
                d0 = k3.date_input("1er paiement", value=D.ajouter_mois(date.today(), 1), format="DD/MM/YYYY")
                if st.form_submit_button("Enregistrer le nouvel échéancier"):
                    D.reechelonner(session, dette, nb, d0, freq)
                    session.commit()
                    config.flash("Nouvel échéancier enregistré.")
                    st.rerun()
            st.markdown("**🚫 Annuler la dette** (erreur de saisie). Les versements reçus restent enregistrés.")
            if st.button("Annuler cette dette", key=f"annul_{dette.id}"):
                D.annuler_dette(session, dette)
                session.commit()
                config.flash("Dette annulée.")
                st.rerun()


# ------------------------------------------------------------------ Dialogues
@st.dialog("💰 Encaisser un versement")
def _dialog_versement(dette_id):
    params = get_params()
    with get_session() as session:
        dette = session.get(Dette, dette_id)
        recu_id = st.session_state.get("recu_cree")
        if recu_id:
            p = session.get(Paiement, recu_id)
            st.success(f"Versement de {fmt_money(p.montant)} enregistré. Reste : {fmt_money(dette.reste)}")
            st.download_button(
                "🧾 Télécharger le reçu",
                documents.recu(p, params),
                f"Recu_R-{p.id:05d}.pdf",
                "application/pdf",
                type="primary",
                use_container_width=True,
            )
            if st.button("Fermer", use_container_width=True):
                st.session_state.pop("recu_cree")
                st.rerun()
            return
        s = D.situation_dette(dette)
        st.markdown(f"**{dette.client.nom}** doit encore **{fmt_money(dette.reste)}**.")
        with st.form("versement"):
            montant = st.number_input(
                "Montant reçu (FCFA)",
                min_value=1,
                max_value=int(round(dette.reste)),
                value=int(min(s["prochain_montant"] or dette.reste, dette.reste)),
                step=500,
            )
            mode = st.selectbox("Moyen de paiement", config.MODES_PAIEMENT)
            note = st.text_input("Référence / note (facultatif)", placeholder="Ex : ID de transaction Wave")
            if st.form_submit_button("Enregistrer le versement", type="primary", use_container_width=True):
                try:
                    p = D.enregistrer_paiement(session, dette, montant, mode, note)
                    session.commit()
                    st.session_state["recu_cree"] = p.id
                    st.rerun(scope="fragment")
                except D.ErreurDette as e:
                    session.rollback()
                    st.error(str(e))


@st.dialog("➕ Nouvelle dette (sans vente)", width="large")
def _dialog_nouvelle_dette():
    st.caption(
        "Pour une ancienne dette (cahier), de l'argent prêté, un service… "
        "Pour vendre des produits à crédit, utilisez **Nouvelle vente**."
    )
    with get_session() as session:
        clients = session.query(Client).filter(Client.nom != config.CLIENT_PASSAGE).order_by(Client.nom).all()
        with st.form("nouvelle_dette"):
            c1, c2 = st.columns(2)
            par_id = {c.id: c for c in clients}
            choix = c1.selectbox(
                "Client existant",
                [None, *par_id],
                format_func=lambda i: "— Nouveau client —" if i is None else f"{par_id[i].nom} · {par_id[i].telephone}",
            )
            client = par_id.get(choix)
            nom = c2.text_input("…ou nouveau client : nom")
            tel = c2.text_input("Téléphone du nouveau client")
            description = st.text_input(
                "Objet de la dette", placeholder="Ex : ancienne dette du cahier, prêt d'argent…"
            )
            m1, m2, m3 = st.columns(3)
            montant = m1.number_input("Montant total dû", min_value=0, step=1000)
            acompte = m2.number_input("Avance versée aujourd'hui", min_value=0, step=500)
            mode = m3.selectbox("Moyen de l'avance", config.MODES_PAIEMENT)
            e1, e2, e3 = st.columns(3)
            nb = e1.number_input("Payer en combien de fois ?", 1, 36, 1)
            freq = e2.selectbox("Tous les…", list(config.FREQUENCES), index=2)
            d0 = e3.date_input("1er paiement", value=D.ajouter_mois(date.today(), 1), format="DD/MM/YYYY")
            if st.form_submit_button("Créer la dette", type="primary", use_container_width=True):
                if client is None:
                    if not nom or not tel:
                        st.error("Choisissez un client ou saisissez le nom et le téléphone du nouveau client.")
                        return
                    client = Client(nom=nom.strip(), telephone=tel.strip())
                    session.add(client)
                    session.flush()
                try:
                    d = D.creer_dette(
                        session,
                        client.id,
                        montant,
                        nb_versements=nb,
                        date_premiere=d0,
                        frequence=freq,
                        acompte=acompte,
                        mode_acompte=mode,
                        description=description or "Dette",
                    )
                    session.commit()
                except D.ErreurDette as e:
                    session.rollback()
                    st.error(str(e))
                    return
                st.session_state["dette_ouverte"] = d.id
                config.flash(
                    f"Dette de {fmt_money(montant)} créée pour {client.nom}. Imprimez la reconnaissance de dette."
                )
                st.rerun()


# ------------------------------------------------------------------ Tous les versements
def _versements(session, params):
    paiements = (
        session.query(Paiement).filter(Paiement.dette_id.isnot(None)).order_by(Paiement.date.desc()).limit(1000).all()
    )
    if not paiements:
        st.info("Aucun versement enregistré.")
        return
    df = pd.DataFrame(
        [
            {
                "Reçu": f"R-{p.id:05d}",
                "Date": p.date.strftime("%d/%m/%Y %H:%M"),
                "Client": p.client.nom,
                "Dette": f"D-{p.dette_id:05d}",
                "Montant": p.montant,
                "Moyen": p.mode,
                "Note": p.note,
            }
            for p in paiements
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={"Montant": st.column_config.NumberColumn(format="localized")},
    )
    st.download_button(
        "⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "versements.csv", "text/csv"
    )
