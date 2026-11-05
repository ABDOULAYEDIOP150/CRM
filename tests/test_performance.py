"""Le nombre de requêtes ne doit pas grandir avec le nombre de dettes, ventes ou produits.

En ligne (Neon), chaque requête est un aller-retour sur internet : une requête par dette ou par vente
rendait l'app très lente. Ces tests comptent les requêtes avec 3 puis 30 enregistrements.
"""

import io
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import event
from sqlalchemy.orm import selectinload

from db import dettes as D
from db import stock as S
from db import tableau as T
from db.alertes import calculer_alertes
from db.models import Client, Produit, Vente, VenteProduit, get_session, init_db
from modules.base_donnees import _export_excel

PARAMS = {"jours_alerte_echeance": "2", "seuil_stock": "5", "jours_stock_dormant": "30"}


def _remplir(s, n):
    for i in range(n):
        c = Client(nom=f"Client {i}", telephone=f"77 000 00 {i:02d}")
        p = Produit(nom=f"Produit {i}", reference=f"P-{i:03d}", stock=0)
        s.add_all([c, p])
        s.flush()
        S.entree_stock(s, p, 10, 1000, 1200)
        v = Vente(client_id=c.id, mode_livraison="Retrait", mode_paiement="Crédit")
        s.add(v)
        s.flush()
        s.add(VenteProduit(vente_id=v.id, produit_id=p.id, quantite=2, prix_unit=1200, cout=S.sortie_stock(s, p, 2)))
        s.flush()
        s.refresh(v)
        D.creer_dette(s, c.id, v.total, nb_versements=2, date_premiere=date.today() - timedelta(days=3), vente_id=v.id)
    s.commit()


def _compter(url, fonction):
    engine = init_db(url)
    n = [0]

    def compte(*_):
        n[0] += 1

    event.listen(engine, "before_cursor_execute", compte)
    try:
        with get_session(url) as s:
            fonction(s)
    finally:
        event.remove(engine, "before_cursor_execute", compte)
    return n[0]


def _lectures(s):
    calculer_alertes(s, PARAMS)
    D.resume_creances(s)
    T.jour(s)
    clients = s.query(Client).options(selectinload(Client.ventes), selectinload(Client.dettes)).all()
    for c in clients:  # comme la page Clients
        sum(d.reste for d in c.dettes) + sum(v.total for v in c.ventes)


def test_requetes_independantes_du_volume(db_url):
    with get_session(db_url) as s:
        _remplir(s, 3)
    petit = _compter(db_url, _lectures)
    with get_session(db_url) as s:  # 27 clients et dettes de plus
        for i in range(27):
            c = Client(nom=f"Autre {i}", telephone=f"78 000 00 {i:02d}")
            s.add(c)
            s.flush()
            D.creer_dette(s, c.id, 5000, nb_versements=3, date_premiere=date.today() - timedelta(days=3))
        s.commit()
    grand = _compter(db_url, _lectures)
    assert grand <= petit + 2, f"{petit} requêtes avec 3 dettes, {grand} avec 30 : une requête par ligne est revenue"


def test_export_excel(db_url):
    with get_session(db_url) as s:
        _remplir(s, 2)
    feuilles = pd.read_excel(io.BytesIO(_export_excel(init_db(db_url))), sheet_name=None)
    assert len(feuilles["clients"]) == 2 and len(feuilles["dettes"]) == 2
