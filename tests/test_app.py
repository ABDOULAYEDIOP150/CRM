"""Test de fumée : chaque page s'affiche sans erreur avec des données de démo."""

import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

PAGES = ["Accueil", "Alertes", "Ventes", "Dettes", "Clients", "Produits", "Documents", "Paramètres", "Base", "Aide"]


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
    at.session_state["page"] = page
    at.run()
    assert not at.exception, at.exception


def _app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(os.path.join(RACINE, "app_crm.py"), default_timeout=30)


def test_option_dette_visible_des_l_ouverture():
    """L'option « À crédit (dette) » doit être visible même avec un panier vide."""
    at = _app()
    at.session_state["page"] = "Ventes"
    at.run()
    assert not at.exception, at.exception
    options = [o for bg in at.button_group for o in bg.options]
    assert any("crédit" in str(o) for o in options), options


def test_vente_a_credit_et_documents():
    from db.models import Client, Dette, Produit, get_session
    from modules.ventes import DETTE

    with get_session() as s:
        avant = s.query(Dette).count()
        pid = s.query(Produit).filter(Produit.stock > 3).first().id
        cid = s.query(Client).filter(Client.nom == "Moussa Fall").first().id
    at = _app()
    at.session_state["page"] = "Ventes"
    at.session_state["panier"] = {pid: 2}
    at.session_state["vente_client"] = cid
    at.session_state["reglement"] = DETTE
    at.run()
    [n for n in at.number_input if n.label == "Avance versée aujourd'hui"][0].set_value(1000).run()
    [n for n in at.number_input if n.label == "Payer en combien de fois ?"][0].set_value(3).run()
    [b for b in at.button if "Valider la vente à crédit" in b.label][0].click().run()
    assert not at.exception, at.exception
    with get_session() as s:
        assert s.query(Dette).count() == avant + 1
        d = s.query(Dette).order_by(Dette.id.desc()).first()
        assert len(d.echeances) == 3 and d.vente_id is not None and d.total_paye == 1000
    # écran de confirmation avec les documents
    assert at.session_state["derniere_vente"] == d.vente_id
    textes = " ".join(m.value for m in at.markdown)
    assert "Vente enregistrée" in textes


def test_documents_pdf():
    from db.models import Dette, get_session
    from db.utils import get_params
    from modules import documents

    p = get_params()
    with get_session() as s:
        d = s.query(Dette).filter(Dette.acompte > 0).first()
        for pdf in [
            documents.reconnaissance_dette(d, p),
            documents.recu(d.paiements[0], p),
            documents.releve_client(d.client, p),
            documents.facture(d.vente, p),
        ]:
            assert pdf[:4] == b"%PDF" and len(pdf) > 1500


def test_connexion_par_mot_de_passe(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_PASSWORD", "dakar2026")
    at = AppTest.from_file(os.path.join(RACINE, "app_crm.py"), default_timeout=30)
    at.run()
    assert not at.exception
    assert not [b for b in at.button if "Clients" in b.label]  # menu caché avant connexion
    at.text_input[0].input("mauvais")
    at.button[0].click().run()
    assert at.error and "incorrect" in at.error[0].value
    at.text_input[0].input("dakar2026")
    at.button[0].click().run()
    assert [b for b in at.button if "Clients" in b.label]


def test_recherche_produit_avec_suggestions():
    """Choisir un produit dans la recherche (ex. « ci » → Ciment) l'ajoute au panier."""
    from db.models import Produit, get_session

    with get_session() as s:
        ciment = s.query(Produit).filter(Produit.nom.ilike("ci%")).first()
        tous = [p.id for p in s.query(Produit)]
    at = _app()
    at.session_state["page"] = "Ventes"
    at.run()
    recherche = at.selectbox(key="recherche_produit")
    assert set(recherche.options) and len(recherche.options) == len(tous)  # tous les produits de la base
    assert "Ciment" in recherche.options[0] or any("Ciment" in o for o in recherche.options)
    recherche.set_value(ciment.id).run()
    assert not at.exception, at.exception
    assert at.session_state["panier"].get(ciment.id) == 1
    assert at.selectbox(key="recherche_produit").value is None  # prêt pour le produit suivant
