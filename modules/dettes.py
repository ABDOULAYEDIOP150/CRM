"""Page 💳 Dettes : suivi des crédits clients, échéancier, remboursements, relances."""

from datetime import date
from urllib.parse import quote

import pandas as pd
import streamlit as st

import config
from config import fmt_date, fmt_money
from db import dettes as D
from db.models import Client, Dette, Paiement, get_session
from db.utils import get_params
from modules.pdf_utils import generer_recu

COULEURS = {
    D.STATUT_RETARD: "#ef4444",
    D.STATUT_A_JOUR: "#2563eb",
    D.STATUT_SOLDEE: "#10b981",
    D.STATUT_ANNULEE: "#94a3b8",
}
ICONES = {D.STATUT_RETARD: "🔴", D.STATUT_A_JOUR: "🟢", D.STATUT_SOLDEE: "✅", D.STATUT_ANNULEE: "⚪"}


def show_dettes():
    st.markdown("<h2 style='color: #1e3a8a;'>💳 Dettes clients</h2>", unsafe_allow_html=True)
    params = get_params()
    with get_session() as session:
        onglets = st.tabs(["📋 Suivi des dettes", "👤 Par client", "➕ Nouvelle dette", "🧾 Remboursements"])
        with onglets[0]:
            _suivi(session, params)
        with onglets[1]:
            _par_client(session, params)
        with onglets[2]:
            _nouvelle_dette(session)
        with onglets[3]:
            _remboursements(session, params)


# ---------------------------------------------------------------- Suivi


def _suivi(session, params):
    r = D.resume_creances(session, jours_alerte=int(params["jours_alerte_echeance"]))
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(config.stat_card("Total à recevoir", fmt_money(r["total_du"])), unsafe_allow_html=True)
    k2.markdown(config.stat_card("Clients débiteurs", r["nb_debiteurs"]), unsafe_allow_html=True)
    k3.markdown(
        config.stat_card(
            "Montant en retard", fmt_money(r["montant_retard"]), config.DANGER_RED, f"{len(r['retards'])} dette(s)"
        ),
        unsafe_allow_html=True,
    )
    k4.markdown(
        config.stat_card(
            "Échéances proches",
            len(r["echeances_proches"]),
            config.WARNING_ORANGE,
            f"dans les {params['jours_alerte_echeance']} jours",
        ),
        unsafe_allow_html=True,
    )

    f1, f2 = st.columns([1, 2])
    with f1:
        filtre = st.selectbox("Statut", ["En cours", "En retard", "À jour", "Soldées", "Toutes"])
    with f2:
        recherche = st.text_input("Rechercher un client", placeholder="Nom ou téléphone")

    toutes = session.query(Dette).order_by(Dette.date_creation.desc()).all()
    lignes = []
    for d in toutes:
        s = D.situation_dette(d)
        if filtre == "En cours" and s["statut"] not in (D.STATUT_RETARD, D.STATUT_A_JOUR):
            continue
        if filtre == "En retard" and s["statut"] != D.STATUT_RETARD:
            continue
        if filtre == "À jour" and s["statut"] != D.STATUT_A_JOUR:
            continue
        if filtre == "Soldées" and s["statut"] != D.STATUT_SOLDEE:
            continue
        if recherche and recherche.lower() not in f"{d.client.nom} {d.client.telephone}".lower():
            continue
        lignes.append((d, s))

    if not lignes:
        st.info("Aucune dette pour ce filtre.")
        return

    df = pd.DataFrame(
        [
            {
                "N°": f"D-{d.id:05d}",
                "Client": d.client.nom,
                "Téléphone": d.client.telephone,
                "Objet": d.description or "—",
                "Date": fmt_date(d.date_creation),
                "Montant": d.montant,
                "Payé": d.total_paye,
                "Reste": d.reste,
                "Prochaine échéance": fmt_date(s["prochaine_date"]),
                "Statut": f"{ICONES[s['statut']]} {s['statut']}"
                + (f" ({s['jours_retard']} j)" if s["jours_retard"] else ""),
            }
            for d, s in lignes
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%d FCFA") for c in ["Montant", "Payé", "Reste"]},
    )
    st.download_button(
        "⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "dettes.csv", "text/csv"
    )

    st.markdown("---")
    choix = config.choisir(
        "Ouvrir une dette",
        [d for d, _ in lignes],
        lambda d: f"D-{d.id:05d} · {d.client.nom} · reste {fmt_money(d.reste)}",
    )
    _detail(session, choix, params)


def _detail(session, dette, params):
    s = D.situation_dette(dette)
    couleur = COULEURS[s["statut"]]
    st.markdown(
        f"""
        <div style='background:white;border-left:6px solid {couleur};padding:1rem 1.2rem;border-radius:10px;'>
            <h3 style='margin:0'>{dette.client.nom} — D-{dette.id:05d}
                <span style='color:{couleur};font-size:1rem'>· {s["statut"]}</span></h3>
            <p style='margin:6px 0 0 0;color:#475569'>{dette.description or ""}
            · créée le {fmt_date(dette.date_creation)} · fréquence {dette.frequence}</p>
            <p style='margin:6px 0 0 0;font-size:1.1rem'>Montant <b>{fmt_money(dette.montant)}</b> ·
            Payé <b>{fmt_money(dette.total_paye)}</b> ·
            Reste <b style='color:{couleur}'>{fmt_money(dette.reste)}</b></p>
        </div>""",
        unsafe_allow_html=True,
    )
    if dette.montant:
        st.progress(
            min(dette.total_paye / dette.montant, 1.0), text=f"{dette.total_paye / dette.montant:.0%} remboursé"
        )

    gauche, droite = st.columns([3, 2])
    with gauche:
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
                            "Payé": l["couvert"],
                            "Reste": l["reste"],
                            "Statut": l["statut"] + (f" ({l['jours_retard']} j)" if l["jours_retard"] else ""),
                        }
                        for l in ech
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={c: st.column_config.NumberColumn(format="%d") for c in ["Prévu", "Payé", "Reste"]},
            )
        st.markdown("##### 🧾 Paiements reçus")
        if dette.paiements:
            for p in reversed(dette.paiements):
                c1, c2 = st.columns([4, 1])
                c1.write(
                    f"{p.date.strftime('%d/%m/%Y %H:%M')} — **{fmt_money(p.montant)}** · {p.mode}"
                    + (f" · _{p.note}_" if p.note else "")
                )
                c2.download_button(
                    "Reçu", generer_recu(p, params), f"Recu_R-{p.id:05d}.pdf", "application/pdf", key=f"recu_{p.id}"
                )
        else:
            st.caption("Aucun paiement pour l'instant.")

    with droite:
        if dette.statut == "en_cours" and dette.reste > 0:
            st.markdown("##### 💰 Enregistrer un paiement")
            with st.form(f"paiement_{dette.id}", clear_on_submit=True):
                montant = st.number_input(
                    "Montant reçu",
                    min_value=0,
                    max_value=int(round(dette.reste)),
                    value=int(min(s["prochain_montant"] or dette.reste, dette.reste)),
                    step=500,
                )
                mode = st.selectbox("Moyen de paiement", config.MODES_PAIEMENT)
                note = st.text_input("Note (optionnel)", placeholder="Ex : réf. transaction Wave")
                if st.form_submit_button("Valider le paiement", use_container_width=True):
                    try:
                        p = D.enregistrer_paiement(session, dette, montant, mode, note)
                        session.commit()
                        st.session_state["flash"] = f"✅ Paiement de {fmt_money(p.montant)} enregistré" + (
                            " — dette soldée 🎉" if dette.statut == "soldee" else "."
                        )
                        st.rerun()
                    except D.ErreurDette as e:
                        session.rollback()
                        st.error(str(e))

            st.markdown("##### 📲 Relancer le client")
            msg = D.message_relance(
                params["message_relance"],
                dette.client,
                dette.reste,
                s["prochaine_date"],
                params["boutique_nom"],
                params["boutique_telephone"],
                fmt_money,
            )
            msg = st.text_area("Message", msg, height=120, key=f"msg_{dette.id}")
            lien = D.lien_whatsapp(dette.client.telephone, msg)
            if lien:
                st.link_button("Envoyer sur WhatsApp", lien, use_container_width=True)
            num = D.normaliser_telephone(dette.client.telephone)
            if num:
                st.link_button("Envoyer par SMS", f"sms:+{num}?body={quote(msg)}", use_container_width=True)

            with st.expander("🔁 Rééchelonner (donner plus de temps)"):
                with st.form(f"reech_{dette.id}"):
                    nb = st.number_input("Nouveau nombre de versements", 1, 36, 2)
                    freq = st.selectbox("Fréquence", list(config.FREQUENCES), key=f"freq_{dette.id}")
                    d0 = st.date_input(
                        "1ère nouvelle échéance", value=D.ajouter_mois(date.today(), 1), format="DD/MM/YYYY"
                    )
                    if st.form_submit_button("Recalculer l'échéancier"):
                        D.reechelonner(session, dette, nb, d0, freq)
                        session.commit()
                        st.session_state["flash"] = "✅ Nouvel échéancier enregistré."
                        st.rerun()

            with st.expander("🚫 Annuler cette dette"):
                st.caption(
                    "À utiliser en cas d'erreur de saisie ou de dette abandonnée. "
                    "Les paiements déjà reçus restent enregistrés."
                )
                if st.button("Confirmer l'annulation", key=f"annul_{dette.id}"):
                    D.annuler_dette(session, dette)
                    session.commit()
                    st.rerun()
        elif s["statut"] == D.STATUT_SOLDEE:
            st.success(f"Dette soldée le {fmt_date(dette.date_solde)} 🎉")


# ---------------------------------------------------------------- Par client


def _par_client(session, params):
    clients = session.query(Client).order_by(Client.nom).all()
    lignes = []
    for c in clients:
        ds = [d for d in c.dettes if d.statut == "en_cours"]
        if not ds and not c.plafond_credit:
            continue
        sits = [D.situation_dette(d) for d in ds]
        encours = sum(d.reste for d in ds)
        lignes.append(
            {
                "Client": c.nom,
                "Téléphone": c.telephone,
                "Dettes en cours": len(ds),
                "Encours": encours,
                "En retard": sum(s["montant_retard"] for s in sits),
                "Retard max (jours)": max((s["jours_retard"] for s in sits), default=0),
                "Plafond": c.plafond_credit or 0,
                "Utilisation plafond": f"{encours / c.plafond_credit:.0%}" if c.plafond_credit else "—",
                "Historique": f"{sum(1 for d in c.dettes if d.statut == 'soldee')} dette(s) soldée(s)",
            }
        )
    if not lignes:
        st.info("Aucun client n'a de dette en cours.")
        return
    df = pd.DataFrame(lignes).sort_values("Encours", ascending=False)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%d FCFA") for c in ["Encours", "En retard", "Plafond"]},
    )


# ---------------------------------------------------------------- Nouvelle dette manuelle


def _nouvelle_dette(session):
    st.caption(
        "Pour une dette qui ne vient pas d'une vente de l'application : ancienne dette (cahier), "
        "argent prêté, service… Les ventes à crédit se font directement dans 🛒 Ventes."
    )
    clients = session.query(Client).order_by(Client.nom).all()
    if not clients:
        st.warning("Ajoutez d'abord un client.")
        return
    with st.form("nouvelle_dette", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            client = config.choisir("Client", clients, lambda c: f"{c.nom} ({c.telephone})")
            montant = st.number_input("Montant total dû (FCFA)", min_value=0, step=1000)
            acompte = st.number_input("Déjà versé aujourd'hui", min_value=0, step=500)
            mode = st.selectbox("Moyen de paiement de l'acompte", config.MODES_PAIEMENT)
        with c2:
            description = st.text_input("Objet", placeholder="Ex : ancienne dette du cahier, prêt…")
            nb = st.number_input("Nombre de versements", 1, 36, 1)
            freq = st.selectbox("Fréquence", list(config.FREQUENCES))
            d0 = st.date_input("1ère échéance", value=D.ajouter_mois(date.today(), 1), format="DD/MM/YYYY")
        if st.form_submit_button("Créer la dette", use_container_width=True):
            try:
                D.creer_dette(
                    session,
                    client.id,
                    montant,
                    nb_versements=nb,
                    date_premiere=d0,
                    frequence=freq,
                    acompte=acompte,
                    mode_acompte=mode,
                    description=description or "Dette manuelle",
                )
                session.commit()
                st.session_state["flash"] = f"✅ Dette de {fmt_money(montant)} créée pour {client.nom}."
                st.rerun()
            except D.ErreurDette as e:
                session.rollback()
                st.error(str(e))


# ---------------------------------------------------------------- Remboursements


def _remboursements(session, params):
    paiements = (
        session.query(Paiement).filter(Paiement.dette_id.isnot(None)).order_by(Paiement.date.desc()).limit(500).all()
    )
    if not paiements:
        st.info("Aucun remboursement enregistré.")
        return
    df = pd.DataFrame(
        [
            {
                "Reçu": f"R-{p.id:05d}",
                "Date": p.date.strftime("%d/%m/%Y %H:%M"),
                "Client": p.client.nom,
                "Dette": f"D-{p.dette_id:05d}",
                "Montant": p.montant,
                "Mode": p.mode,
                "Note": p.note,
            }
            for p in paiements
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={"Montant": st.column_config.NumberColumn(format="%d FCFA")},
    )
    st.download_button(
        "⬇️ Exporter (CSV)", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "remboursements.csv", "text/csv"
    )
