import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import dettes as D  # noqa: E402
from db.alertes import calculer_alertes, compter  # noqa: E402
from db.models import Client, Produit, Vente, VenteProduit, get_session  # noqa: E402

PARAMS = {"jours_alerte_echeance": "2", "seuil_stock": "5", "jours_stock_dormant": "30"}
AUJ = date(2026, 10, 22)


@pytest.fixture
def session(tmp_path):
    s = get_session(f"sqlite:///{tmp_path / 'a.db'}")
    yield s
    s.close()


def _types(alertes):
    return {(a.type, a.titre) for a in alertes}


def test_alertes_dettes(session):
    awa = Client(nom="Awa", telephone="771234567", plafond_credit=10000)
    ali = Client(nom="Ali", telephone="781234567")
    bob = Client(nom="Bob", telephone="701234567")
    session.add_all([awa, ali, bob])
    session.flush()
    D.creer_dette(session, awa.id, 20000, date_premiere=date(2026, 10, 1))  # en retard + plafond
    D.creer_dette(session, ali.id, 5000, date_premiere=AUJ + timedelta(days=2))  # dans 2 jours
    D.creer_dette(session, bob.id, 5000, date_premiere=AUJ + timedelta(days=10))  # trop loin
    a = calculer_alertes(session, PARAMS, AUJ)
    t = _types(a)
    assert ("dette_retard", "Awa") in t and ("plafond", "Awa") in t
    assert ("echeance_proche", "Ali") in t
    assert not any(x.titre == "Bob" for x in a)
    assert a[0].type == "dette_retard"  # le plus urgent en premier
    assert "dans 2 jours" in next(x for x in a if x.titre == "Ali").detail


def test_alertes_stock(session):
    ciment = Produit(nom="Ciment 50 kg", prix=4500, prix_achat=4000, stock=0, unite="sac")
    fer = Produit(nom="Fer 10", prix=3000, prix_achat=2500, stock=3, unite="barre")
    clou = Produit(nom="Clous", prix=900, prix_achat=1000, stock=50, seuil_alerte=10)
    vieux = Produit(nom="Brouette", prix=25000, prix_achat=20000, stock=4, seuil_alerte=1)
    session.add_all([ciment, fer, clou, vieux])
    session.flush()
    v = Vente(client_id=None, date=datetime(2026, 10, 20))
    session.add(v)
    session.flush()
    session.add(VenteProduit(vente_id=v.id, produit_id=clou.id, quantite=1, prix_unit=900))
    session.flush()
    t = _types(calculer_alertes(session, PARAMS, AUJ))
    assert ("rupture", "Ciment 50 kg") in t
    assert ("stock_faible", "Fer 10") in t
    assert ("perte", "Clous") in t and ("stock_faible", "Clous") not in t
    assert ("dormant", "Brouette") in t and ("dormant", "Clous") not in t
    c = compter(calculer_alertes(session, PARAMS, AUJ))
    assert c["rupture"] == 1 and c["critique"] >= 1
