import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import dettes as D  # noqa: E402
from db.models import Client, get_session  # noqa: E402


@pytest.fixture
def session(tmp_path):
    s = get_session(f"sqlite:///{tmp_path / 'test.db'}")
    yield s
    s.close()


@pytest.fixture
def client(session):
    c = Client(nom="Moussa Fall", telephone="77 123 45 67")
    session.add(c)
    session.flush()
    return c


def test_echeancier_arrondi_et_dates():
    lignes = D.generer_echeancier(100000, 3, date(2026, 1, 31), "Mensuelle")
    assert [m for _, m in lignes] == [33333, 33333, 33334]
    assert [d for d, _ in lignes] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]
    hebdo = D.generer_echeancier(30000, 3, date(2026, 1, 1), "Hebdomadaire")
    assert [d for d, _ in hebdo] == [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15)]


def test_creation_avec_acompte(session, client):
    d = D.creer_dette(
        session,
        client.id,
        50000,
        nb_versements=2,
        date_premiere=date(2026, 11, 1),
        acompte=10000,
        date_creation=datetime(2026, 10, 1),
    )
    assert d.total_paye == 10000 and d.reste == 40000
    assert sum(e.montant_prevu for e in d.echeances) == 40000
    s = D.situation_dette(d, date(2026, 10, 15))
    assert s["statut"] == D.STATUT_A_JOUR and s["prochaine_date"] == date(2026, 11, 1)


def test_retard_puis_paiement(session, client):
    d = D.creer_dette(
        session, client.id, 30000, nb_versements=3, date_premiere=date(2026, 9, 1), date_creation=datetime(2026, 8, 1)
    )
    s = D.situation_dette(d, date(2026, 10, 5))
    assert s["statut"] == D.STATUT_RETARD
    assert s["montant_retard"] == 20000 and s["jours_retard"] == 34
    D.enregistrer_paiement(session, d, 15000)
    lignes = D.etat_echeances(d, date(2026, 10, 5))
    assert [l["statut"] for l in lignes] == ["Payée", "En retard", "À venir"]
    assert lignes[1]["reste"] == 5000
    D.enregistrer_paiement(session, d, 15000)
    assert d.statut == "soldee" and D.situation_dette(d)["statut"] == D.STATUT_SOLDEE


def test_paiement_trop_eleve_refuse(session, client):
    d = D.creer_dette(session, client.id, 10000)
    with pytest.raises(D.ErreurDette):
        D.enregistrer_paiement(session, d, 20000)


def test_reechelonnement(session, client):
    d = D.creer_dette(
        session, client.id, 40000, nb_versements=2, date_premiere=date(2026, 8, 1), date_creation=datetime(2026, 7, 1)
    )
    D.enregistrer_paiement(session, d, 10000)
    assert D.situation_dette(d, date(2026, 10, 1))["statut"] == D.STATUT_RETARD
    D.reechelonner(session, d, 3, date(2026, 11, 1), "Mensuelle")
    assert sum(e.montant_prevu for e in d.echeances) == 30000
    assert D.situation_dette(d, date(2026, 10, 1))["statut"] == D.STATUT_A_JOUR


def test_resume_et_encours(session, client):
    D.creer_dette(session, client.id, 20000, date_premiere=date(2026, 9, 1))
    D.creer_dette(session, client.id, 10000, date_premiere=date(2026, 10, 24))
    r = D.resume_creances(session, date(2026, 10, 22), jours_alerte=3)
    assert r["total_du"] == 30000 and r["montant_retard"] == 20000
    assert len(r["retards"]) == 1 and len(r["echeances_proches"]) == 1
    assert D.encours_client(session, client.id) == 30000


def test_whatsapp():
    assert D.normaliser_telephone("77 123 45 67") == "221771234567"
    assert D.normaliser_telephone("+221 77 123 45 67") == "221771234567"
    assert D.lien_whatsapp("771234567", "Bonjour").startswith("https://wa.me/221771234567?text=")


def test_montant_en_lettres():
    from db.lettres import en_lettres

    assert en_lettres(71) == "soixante et onze"
    assert en_lettres(80) == "quatre-vingts"
    assert en_lettres(80000) == "quatre-vingt mille"
    assert en_lettres(17500) == "dix-sept mille cinq cents"
    assert en_lettres(2500000) == "deux millions cinq cent mille"
