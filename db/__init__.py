"""
Package de la couche base de données.

- models.py : modèles SQLAlchemy (clients, produits, ventes, dettes, échéances, paiements, paramètres)
- dettes.py : logique métier des dettes (échéancier, paiements, retards, relances)
- utils.py  : statistiques et paramètres
"""
from .models import (Base, Client, Produit, Vente, VenteProduit, HistoriqueVente, Dette, Echeance,
                     Paiement, Parametre, init_db, get_session)

__version__ = "3.0.0"
