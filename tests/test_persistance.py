"""Les données saisies doivent survivre à un redémarrage de l'application.

C'est le cas réel sur Streamlit Cloud : l'app redémarre souvent, et seule la base (PostgreSQL) garde
les données. Chaque étape tourne dans un processus Python séparé, comme un vrai redémarrage.
Sur SQLite, le fichier temporaire joue le rôle de la base ; sur PostgreSQL (CRM_TEST_PG_URL), c'est la vraie base.
"""

import os
import subprocess
import sys

import pytest

from db.models import normaliser_url

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAISIE = """
from datetime import datetime
from streamlit.testing.v1 import AppTest
from db import dettes as D
from db.models import Client, Paiement, Produit, Vente, VenteProduit, get_session
from db.stock import entree_stock, sortie_stock

# 1) Par l'interface : la page Paramètres, comme le ferait le commerçant
at = AppTest.from_file("app_crm.py", default_timeout=60)
at.session_state["page"] = "Paramètres"
at.run()
[t for t in at.text_input if t.label == "Nom de la boutique"][0].input("Quincaillerie Persistante")
[b for b in at.button if "Enregistrer" in b.label][0].click().run()
assert not at.exception, at.exception

# 2) Un client, un produit, une vente à crédit avec acompte (le parcours complet de la caisse)
with get_session() as s:
    c = Client(nom="Khadija Persistante", telephone="77 999 88 77")
    p = Produit(nom="Ciment test", reference="CIM-TST", stock=0)
    s.add_all([c, p])
    s.flush()
    entree_stock(s, p, 10, 4000, 4600, "SOCOCIM")
    v = Vente(client_id=c.id, mode_livraison="Retrait en magasin", mode_paiement="Crédit")
    s.add(v)
    s.flush()
    cout = sortie_stock(s, p, 3, "Vente")
    s.add(VenteProduit(vente_id=v.id, produit_id=p.id, quantite=3, prix_unit=4600, cout=cout))
    s.flush()
    s.refresh(v)
    D.creer_dette(s, c.id, v.total, nb_versements=2, acompte=3800, mode_acompte="Wave", vente_id=v.id)
    s.commit()
print("SAISIE OK")
"""

LECTURE_APRES_REDEMARRAGE = """
from db.models import Client, Dette, Produit, get_session
from db.utils import get_params
with get_session() as s:
    c = s.query(Client).filter_by(nom="Khadija Persistante").one()
    p = s.query(Produit).filter_by(reference="CIM-TST").one()
    d = s.query(Dette).filter_by(client_id=c.id).one()
    print("CLIENT", c.telephone)
    print("STOCK", p.stock)
    print("DETTE", int(d.montant), int(d.reste), len(d.echeances))
print("BOUTIQUE", get_params()["boutique_nom"])

# La page d'accueil se relance sur ces données sans erreur
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app_crm.py", default_timeout=60)
at.run()
assert not at.exception, at.exception
print("APP OK")
"""


def _lancer(code, url):
    env = {**os.environ, "CRM_DB_URL": url, "DEMO_MODE": "false"}
    r = subprocess.run([sys.executable, "-c", code], cwd=RACINE, env=env, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_client_saisi_conserve_apres_redemarrage(db_url):
    assert "SAISIE OK" in _lancer(SAISIE, db_url)
    sortie = _lancer(LECTURE_APRES_REDEMARRAGE, db_url)  # nouveau processus = app redémarrée
    assert "CLIENT 77 999 88 77" in sortie
    assert "STOCK 7" in sortie
    assert "DETTE 13800 10000 2" in sortie  # 3 × 4600, acompte 3800
    assert "BOUTIQUE Quincaillerie Persistante" in sortie
    assert "APP OK" in sortie


@pytest.mark.parametrize(
    "copiee, attendue",
    [
        ("postgres://u:p@h:5432/crm", "postgresql+psycopg://u:p@h:5432/crm"),  # Supabase, Heroku
        ("postgresql://u:p@h/crm?sslmode=require", "postgresql+psycopg://u:p@h/crm?sslmode=require"),  # Neon
        (' "postgresql://u:p@h/crm" ', "postgresql+psycopg://u:p@h/crm"),  # collée avec guillemets / espaces
        ("postgresql+psycopg://u:p@h/crm", "postgresql+psycopg://u:p@h/crm"),
        ("sqlite:///crm.db", "sqlite:///crm.db"),
    ],
)
def test_adresse_normalisee(copiee, attendue):
    assert normaliser_url(copiee) == attendue


def test_corriger_un_prix_d_achat_mal_saisi(db_url):
    """36 000 tapé au lieu de 11 000 : la correction répare le lot, le prix moyen et la marge des ventes faites."""
    from db.models import Client, Produit, Vente, VenteProduit, get_session
    from db.stock import corriger_prix_lot, entree_stock, sortie_stock

    with get_session(db_url) as s:
        p = Produit(nom="Sable de mer", prix=15000, stock=0, unite="m³")
        c = Client(nom="Awa", telephone="770000000")
        s.add_all([p, c])
        s.flush()
        entree_stock(s, p, 5, 11000, 15000, "SOCOCIM")
        lot = entree_stock(s, p, 3, 36000, 15000, "Autre")
        v = Vente(client_id=c.id)
        s.add(v)
        s.flush()
        cout = sortie_stock(s, p, 6, "Vente")  # 5 du 1er lot + 1 du lot mal saisi
        s.add(VenteProduit(vente_id=v.id, produit_id=p.id, quantite=6, prix_unit=15000, cout=cout))
        s.commit()
        assert cout == 5 * 11000 + 36000
        corriger_prix_lot(s, lot, 12000)
        s.commit()
        ligne = s.query(VenteProduit).one()
        assert ligne.cout == 5 * 11000 + 12000
        assert p.prix_achat == 12000 and lot.prix_achat == 12000
