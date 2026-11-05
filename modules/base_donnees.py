"""Sauvegarde : export de toutes les données dans un fichier Excel (utilisé par la page Paramètres)."""

import io

import pandas as pd
from sqlalchemy import inspect, select

from db.models import Base


def _export_excel(engine):
    """Une feuille par table, une seule requête par table (pas de lecture du schéma)."""
    xlsx = io.BytesIO()
    with engine.connect() as conn, pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        for table in Base.metadata.sorted_tables:
            if inspect(conn).has_table(table.name):
                pd.read_sql_query(select(table), conn).to_excel(w, sheet_name=table.name[:31], index=False)
    return xlsx.getvalue()
