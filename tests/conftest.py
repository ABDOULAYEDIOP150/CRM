"""Choix de la base pour les tests.

Par défaut : un fichier SQLite temporaire par test.
Avec la variable CRM_TEST_PG_URL (ex. postgresql://crm:crm@localhost:5432/crm_test), les mêmes tests
tournent sur une vraie base PostgreSQL, vidée avant chaque test. C'est ce que fait la CI.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PG_URL = os.environ.get("CRM_TEST_PG_URL")


def vider_postgres(url):
    """Supprime toutes les tables pour repartir d'une base vide."""
    import db.models as m

    for eng in m._ENGINES.values():
        eng.dispose()
    m._ENGINES.clear()
    engine = create_engine(m.normaliser_url(url))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    # Les tables sont recréées tout de suite : une connexion restée en cache (modules rechargés
    # par le test de l'app) retrouve ainsi une base prête et vide.
    m.Base.metadata.create_all(engine)
    engine.dispose()


@pytest.fixture
def db_url(tmp_path):
    """URL d'une base vide, propre à ce test."""
    if PG_URL:
        vider_postgres(PG_URL)
        return PG_URL
    return f"sqlite:///{tmp_path / 'test.db'}"
