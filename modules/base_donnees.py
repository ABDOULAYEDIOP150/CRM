"""Base de données : où sont stockées les données, combien, sauvegarde et export."""

import io
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import func, inspect, select

import config
from db.models import Base, get_session, init_db


def _description(url):
    if url.startswith("sqlite"):
        chemin = Path(url.replace("sqlite:///", "", 1)).resolve()
        return "SQLite (fichier)", str(chemin), chemin
    hote = url.split("@")[-1].split("/")[0] if "@" in url else "?"
    return "PostgreSQL", f"serveur {hote}", None


def _export_excel(engine):
    """Une feuille par table, une seule requête par table (pas de lecture du schéma)."""
    xlsx = io.BytesIO()
    with engine.connect() as conn, pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        for table in Base.metadata.sorted_tables:
            if inspect(conn).has_table(table.name):
                pd.read_sql_query(select(table), conn).to_excel(w, sheet_name=table.name[:31], index=False)
    return xlsx.getvalue()


def _temps_de_reponse(engine, essais=3):
    """Aller-retour moyen application -> base (ms) : mesure la distance réseau entre les deux serveurs."""
    import time

    try:
        with engine.connect() as conn:
            conn.execute(select(1))  # connexion établie hors mesure
            t = time.perf_counter()
            for _ in range(essais):
                conn.execute(select(1))
            return (time.perf_counter() - t) / essais * 1000
    except Exception:
        return None


def show_base():
    engine = init_db()
    url = str(engine.url)
    type_db, ou, fichier = _description(url)
    config.entete("Base de données", "Stockage, sauvegarde et export")

    ms = _temps_de_reponse(engine)
    etat = "Fichier local : faites des sauvegardes régulières" if fichier is not None else "En ligne"
    config.kpis(
        [
            ("Type", type_db, config.SECONDARY_BLUE, etat),
            ("Emplacement", ou.replace("serveur ", ""), config.MUTED, ""),
            (
                "Temps de réponse",
                f"{ms:.0f} ms" if ms is not None else "",
                config.SUCCESS_GREEN if ms is not None and ms < 80 else config.WARNING_ORANGE,
                ("très bon" if ms < 30 else "correct" if ms < 80 else "lent") if ms is not None else "",
            ),
        ]
    )
    st.write("")

    with get_session() as s:
        comptes = {}
        noms = {
            "clients": "Clients",
            "produits": "Produits",
            "ventes": "Ventes",
            "dettes": "Dettes",
            "paiements": "Paiements",
            "echeances": "Échéances",
        }
        for table in Base.metadata.sorted_tables:
            if table.name in noms:
                comptes[noms[table.name]] = s.execute(select(func.count()).select_from(table)).scalar()
    config.kpis([(k, v, config.SECONDARY_BLUE, "") for k, v in comptes.items()])

    st.write("")
    st.markdown("#### Sauvegarde")
    c1, c2 = st.columns(2)
    # L'export lit toutes les tables : on ne le prépare que sur demande (sinon la page est lente en ligne).
    if "export_xlsx" not in st.session_state:
        if c1.button("Préparer l'export Excel", width="stretch", type="primary"):
            st.session_state["export_xlsx"] = _export_excel(engine)
            st.rerun()
    else:
        c1.download_button(
            "Télécharger l'export Excel",
            st.session_state.pop("export_xlsx"),
            "crm_export.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            type="primary",
        )
    if fichier is not None and fichier.exists():
        c2.download_button(
            "Télécharger le fichier de la base (.db)",
            fichier.read_bytes(),
            "crm_sauvegarde.db",
            "application/octet-stream",
            width="stretch",
        )

    with st.expander("Utiliser une base PostgreSQL (pour l'application en ligne)"):
        st.markdown(
            "1. Créez une base gratuite sur **Neon** (neon.tech) ou **Supabase** (supabase.com).\n"
            "2. Copiez l'adresse de connexion (elle commence par `postgresql://`).\n"
            "3. Sur Streamlit Cloud : *Settings → Secrets*, ajoutez :\n"
            '```toml\n[database]\nurl = "postgresql://utilisateur:motdepasse@hote/crm?sslmode=require"\n```\n'
            "4. En local : variable d'environnement `CRM_DB_URL` ou fichier `.streamlit/secrets.toml`.\n\n"
            "Les tables sont créées automatiquement au premier lancement.\n\n"
            "**Temps de réponse élevé ?** Chaque clic interroge la base : plus elle est loin du serveur de "
            "l'application, plus l'app attend. Choisissez pour la base la même région que l'hébergeur de l'app."
        )
