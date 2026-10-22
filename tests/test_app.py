"""Test de fumée : chaque page s'affiche sans erreur avec des données de démo."""
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

PAGES = ["Dashboard", "Clients", "Produits", "Ventes", "Dettes", "Factures", "Historique", "Paramètres"]


@pytest.fixture(scope="module", autouse=True)
def base_demo(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "crm.db"
    os.environ["CRM_DB_URL"] = f"sqlite:///{db}"
    import db.models as m
    m.DB_URL = os.environ["CRM_DB_URL"]
    import demo_data
    demo_data.main()
    yield


@pytest.mark.parametrize("page", PAGES)
def test_page(page):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(RACINE, "app_crm.py"), default_timeout=30)
    at.session_state["menu_choice"] = page
    at.run()
    assert not at.exception, at.exception


def test_vente_a_credit():
    from streamlit.testing.v1 import AppTest
    from db.models import get_session, Dette, Produit
    with get_session() as s:
        avant = s.query(Dette).count()
        pid = s.query(Produit).filter(Produit.stock > 3).first().id
    at = AppTest.from_file(os.path.join(RACINE, "app_crm.py"), default_timeout=30)
    at.session_state["menu_choice"] = "Ventes"
    at.session_state["panier"] = {pid: 2}
    at.run()
    [r for r in at.radio if r.label == "Type de paiement"][0].set_value("À crédit (dette)").run()
    [n for n in at.number_input if n.label == "Nombre de versements"][0].set_value(3).run()
    [b for b in at.button if "Valider la vente" in b.label][0].click().run()
    assert not at.exception, at.exception
    with get_session() as s:
        assert s.query(Dette).count() == avant + 1
        d = s.query(Dette).order_by(Dette.id.desc()).first()
        assert len(d.echeances) == 3 and d.vente_id is not None
