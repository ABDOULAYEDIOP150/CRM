"""Calculs du nouveau tableau de bord : courbe d'évolution et clients récents."""

from datetime import datetime, timedelta

import config
from db import tableau as T
from db.models import Client, Produit, Vente, VenteProduit, get_session


def _vente(s, client, jours, montant, remise=0):
    v = Vente(client_id=client.id, date=datetime.now() - timedelta(days=jours), mode_livraison="Retrait", remise=remise)
    s.add(v)
    s.flush()
    p = s.query(Produit).first()
    s.add(VenteProduit(vente_id=v.id, produit_id=p.id, quantite=2, prix_unit=montant / 2))
    s.flush()


def test_evolution_et_clients_recents(db_url):
    with get_session(db_url) as s:
        s.add(Produit(nom="Ciment", reference="CIM-001", stock=100, prix=4600))
        awa, moussa = Client(nom="Awa Ndiaye", telephone="1"), Client(nom="Moussa Fall", telephone="2")
        passage = Client(nom=config.CLIENT_PASSAGE, telephone="")
        s.add_all([awa, moussa, passage])
        s.flush()
        _vente(s, awa, 20, 10000)
        _vente(s, moussa, 5, 8000, remise=1000)  # total 7 000
        _vente(s, passage, 1, 3000)
        _vente(s, awa, 0, 2000)
        s.commit()

        for periode in ["Cette semaine", "30 derniers jours", "Cette année"]:
            debut, fin = config.get_date_range(periode)
            points = T.evolution(s, debut, fin)
            # la courbe additionne exactement le chiffre d'affaires de la période
            assert sum(v for _, v in points) == T.resume_ventes(s, debut, fin)["ca"], periode

        debut, fin = config.get_date_range("30 derniers jours")
        assert len(T.evolution(s, debut, fin)) == 5  # 30 jours -> 5 tranches de 7 jours

        recents = T.clients_recents(s, 5)
        assert [(c.nom, m) for c, m, _ in recents] == [("Awa Ndiaye", 2000), ("Moussa Fall", 7000)]
