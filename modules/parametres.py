import streamlit as st

import config
from db.utils import get_params, set_params


def show_parametres():
    config.entete(
        "Paramètres",
        "Ces informations apparaissent sur les factures, reçus, reconnaissances de dette et messages de relance.",
    )
    p = get_params()
    with st.form("parametres"):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom de la boutique", p["boutique_nom"])
            adresse = st.text_input("Adresse", p["boutique_adresse"])
            tel = st.text_input("Téléphone (Wave / Orange Money)", p["boutique_telephone"])
            email = st.text_input("Email", p["boutique_email"])
        with c2:
            ninea = st.text_input("NINEA", p["boutique_ninea"])
            rccm = st.text_input("RCCM", p["boutique_rccm"])
            seuil = st.number_input("Seuil général de stock faible", min_value=0, value=int(p["seuil_stock"]))
            jours = st.number_input(
                "Alerter combien de jours avant un paiement prévu ?",
                min_value=0,
                max_value=30,
                value=int(p["jours_alerte_echeance"]),
            )
            dormant = st.number_input(
                "Signaler un produit non vendu depuis (jours)",
                min_value=7,
                max_value=365,
                value=int(p["jours_stock_dormant"]),
            )
        msg = st.text_area(
            "Modèle du message de relance",
            p["message_relance"],
            height=110,
            help="Variables : {client} {reste} {echeance} {boutique} {telephone}",
        )
        if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
            set_params(
                {
                    "boutique_nom": nom,
                    "boutique_adresse": adresse,
                    "boutique_telephone": tel,
                    "boutique_email": email,
                    "boutique_ninea": ninea,
                    "boutique_rccm": rccm,
                    "seuil_stock": seuil,
                    "jours_alerte_echeance": jours,
                    "jours_stock_dormant": dormant,
                    "message_relance": msg,
                }
            )
            config.flash("Paramètres enregistrés.")
            st.rerun()
    if st.button("Rétablir le message de relance par défaut"):
        set_params({"message_relance": config.PARAMETRES_DEFAUT["message_relance"]})
        st.rerun()

    # ---------- Apparence ----------
    st.markdown("#### 🎨 Apparence : police d'écriture")
    actuelle = p.get("police", "Inter")
    noms = list(config.POLICES)
    a, b = st.columns([2, 3], vertical_alignment="center")
    choix = a.selectbox("Police", noms, index=noms.index(actuelle) if actuelle in noms else 0,
                        format_func=lambda n: f"{n} — {config.POLICES[n]}")  # fmt: skip
    url = "https://fonts.googleapis.com/css2?family=" + choix.replace(" ", "+") + ":wght@400;700&display=swap"
    b.markdown(
        f"<style>@import url('{url}');</style><div style=\"font-family:'{choix}',sans-serif;font-size:1.15rem;"
        f'border:1px solid #e2e8f0;border-radius:10px;padding:.7rem 1rem;background:#fff">'
        f"<b>Ciment CPJ 45 — 4 600 FCFA</b><br>Aperçu : Awa Ndiaye doit 15 000 FCFA, à payer le 24/10.</div>",
        unsafe_allow_html=True,
    )
    if choix != actuelle and st.button(f"Appliquer la police {choix}", type="primary"):
        set_params({"police": choix})
        config.flash(f"Police {choix} appliquée.")
        st.rerun()
