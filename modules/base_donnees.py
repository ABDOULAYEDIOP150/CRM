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


def show_base():
    engine = init_db()
    url = str(engine.url)
    type_db, ou, fichier = _description(url)
    config.entete("Base de données", "Toutes les données de l'application sont enregistrées ici.")

    st.markdown(f"**Type :** {type_db}  \n**Emplacement :** `{ou}`")
    if fichier is not None:
        st.info(
            "Les données sont enregistrées dans le fichier ci-dessus, sur l'ordinateur qui fait tourner l'application. "
            "Faites une **sauvegarde régulière** (bouton plus bas).  \n"
            "⚠️ Sur un hébergement en ligne comme Streamlit Cloud, ce fichier est **effacé à chaque redémarrage** : "
            "il faut alors une base PostgreSQL (voir en bas de page)."
        )
    else:
        st.success("Base PostgreSQL en ligne : les données sont conservées même si l'application redémarre.")

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

    st.markdown("#### 💾 Sauvegarde")
    c1, c2 = st.columns(2)
    xlsx = io.BytesIO()
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        for table in inspect(engine).get_table_names():
            pd.read_sql_table(table, engine).to_excel(w, sheet_name=table[:31], index=False)
    c1.download_button(
        "📊 Tout exporter en Excel",
        xlsx.getvalue(),
        "crm_export.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
    if fichier is not None and fichier.exists():
        c2.download_button(
            "🗄️ Télécharger le fichier de la base (.db)",
            fichier.read_bytes(),
            "crm_sauvegarde.db",
            "application/octet-stream",
            use_container_width=True,
        )

    with st.expander("Utiliser une base PostgreSQL (pour l'application en ligne)"):
        st.markdown(
            "1. Créez une base gratuite sur **Neon** (neon.tech) ou **Supabase** (supabase.com).\n"
            "2. Copiez l'adresse de connexion (elle commence par `postgresql://`).\n"
            "3. Sur Streamlit Cloud : *Settings → Secrets*, ajoutez :\n"
            '```toml\n[database]\nurl = "postgresql://utilisateur:motdepasse@hote/crm?sslmode=require"\n```\n'
            "4. En local : variable d'environnement `CRM_DB_URL` ou fichier `.streamlit/secrets.toml`.\n\n"
            "Les tables sont créées automatiquement au premier lancement."
        )
