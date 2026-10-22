import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import stock as S  # noqa: E402
from db.models import LotStock, MouvementStock, Produit, get_session  # noqa: E402


@pytest.fixture
def session(tmp_path):
    s = get_session(f"sqlite:///{tmp_path / 's.db'}")
    yield s
    s.close()


def test_code_produit(session):
    session.add(Produit(nom="Sable fin", reference=S.generer_code(session, "Sable fin"), stock=0))
    session.flush()
    assert S.generer_code(session, "Sable de mer") == "SAB-002"
    assert S.generer_code(session, "Écrou 10") == "ECR-001"


def test_entrees_puis_vente_fifo(session):
    p = Produit(nom="Ciment", reference="CIM-001", stock=0)
    session.add(p)
    S.entree_stock(session, p, 10, 4000, 4600, fournisseur="SOCOCIM")
    S.entree_stock(session, p, 10, 4300, 4800)  # le prix fournisseur a augmenté
    assert p.stock == 20 and p.prix == 4800 and p.prix_achat == 4150  # moyenne pondérée
    cout = S.sortie_stock(session, p, 12, "Vente")
    assert cout == 10 * 4000 + 2 * 4300  # les 10 anciens d'abord, puis 2 du nouveau lot
    assert p.stock == 8 and p.prix_achat == 4300
    assert [l.restant for l in p.lots] == [0, 8]
    with pytest.raises(S.ErreurStock):
        S.sortie_stock(session, p, 9)
    assert session.query(MouvementStock).count() == 3


def test_inventaire_et_reprise(session):
    p = Produit(nom="Clous", reference="CLO-001", stock=5, prix_achat=900, prix=1200)  # ancien stock sans lot
    session.add(p)
    session.flush()
    S.synchroniser_lots(session)
    assert session.query(LotStock).count() == 1 and p.lots[0].prix_achat == 900
    S.fixer_stock(session, p, 3)
    assert p.stock == 3
    S.fixer_stock(session, p, 7)
    assert p.stock == 7 and len(p.lots) == 2
