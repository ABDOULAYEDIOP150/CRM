"""
Package de la couche base de données.

- models.py : modèles SQLAlchemy (clients, produits, ventes, dettes, échéances, paiements, paramètres)
- dettes.py : logique métier des dettes (échéancier, paiements, retards, relances)
- utils.py  : statistiques et paramètres
"""

from .models import (
    Base,
    Client,
    Dette,
    Echeance,
    HistoriqueVente,
    Paiement,
    Parametre,
    Produit,
    Vente,
    VenteProduit,
    get_session,
    init_db,
)

__all__ = [
    "Base",
    "Client",
    "Dette",
    "Echeance",
    "HistoriqueVente",
    "Paiement",
    "Parametre",
    "Produit",
    "Vente",
    "VenteProduit",
    "get_session",
    "init_db",
]
__version__ = "3.1.0"
