import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import import_produits as I  # noqa: E402
from db.models import MouvementStock, Produit, get_session  # noqa: E402


@pytest.fixture
def session(tmp_path):
    s = get_session(f"sqlite:///{tmp_path / 'i.db'}")
    s.add(Produit(nom="Ciment 50 kg", prix=4500, prix_achat=4000, stock=10, reference="CIM50"))
    s.flush()
    yield s
    s.close()


def test_colonnes_et_nombres():
    cols = I.reconnaitre_colonnes(["Désignation", "Qté", "PV", "Prix d'achat", "Famille"])
    assert cols == {"nom": "Désignation", "stock": "Qté", "prix": "PV", "prix_achat": "Prix d'achat",
                    "categorie": "Famille"}  # fmt: skip
    assert I.nombre("4 600 FCFA") == 4600 and I.nombre("12.500") == 12500 and I.nombre("") is None
    with pytest.raises(ValueError):
        I.nombre("beaucoup")


def test_analyse_et_import(session):
    df = pd.DataFrame({
        "Désignation": ["ciment 50 kg", "Café Touba", "Tôle", "Clous", ""],
        "PV": ["4 700", "1000", None, "abc", None],
        "Qté": [5, 40, 3, 1, None],
        "Unité": ["Sac", "paquet", "pièce", "kg", None],
    })  # fmt: skip
    lignes, _ = I.analyser(session, df)
    actions = {l["nom"]: l["action"] for l in lignes}
    assert actions == {"ciment 50 kg": I.MAJ, "Café Touba": I.NOUVEAU, "Tôle": I.ERREUR, "Clous": I.ERREUR}
    compte = I.appliquer(session, lignes, mode_stock="ajouter")
    assert compte == {I.NOUVEAU: 1, I.MAJ: 1}
    ciment = session.query(Produit).filter_by(reference="CIM50").one()
    assert ciment.prix == 4700 and ciment.stock == 15 and ciment.unite == "sac"
    cafe = session.query(Produit).filter_by(nom="Café Touba").one()
    assert cafe.stock == 40 and cafe.categorie == "Divers"
    assert session.query(MouvementStock).count() == 2


def test_modele_relu(session):
    contenu = I.modele_excel(session.query(Produit).all())
    df = I.lire_fichier("catalogue.xlsx", contenu)
    lignes, cols = I.analyser(session, df)
    assert len(cols) == 8 and lignes[0]["action"] in (I.INCHANGE, I.MAJ)
