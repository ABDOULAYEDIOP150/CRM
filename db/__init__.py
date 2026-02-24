"""
Package de la couche base de données
Ce module initialise les composants d'accès aux données
"""
from .models import Base, Client, Produit, Vente, VenteProduit, HistoriqueVente, init_db, get_session
from .utils import get_stats_periode, get_top_produits, get_evolution_ca, get_repartition_modes_livraison

# Version du package DB
__version__ = "1.0.0"

# Exports principaux pour faciliter l'import
__all__ = [
    # Modèles
    "Base",
    "Client",
    "Produit",
    "Vente",
    "VenteProduit",
    "HistoriqueVente",
    "init_db",
    "get_session",
    
    # Utilitaires
    "get_stats_periode",
    "get_top_produits",
    "get_evolution_ca",
    "get_repartition_modes_livraison"
]

# Initialisation rapide (optionnel)
def init_db_quick():
    """Fonction rapide pour initialiser la base de données"""
    engine = init_db()
    return get_session()

# Documentation du package
__doc__ = """
Package DB pour CRM Professionnel
=================================

Ce package gère toutes les interactions avec la base de données SQLite.

Modules:
    - models.py: Définition des modèles SQLAlchemy
    - utils.py: Fonctions utilitaires pour les requêtes

Utilisation typique:
    from db import get_session, Client
    session = get_session()
    clients = session.query(Client).all()
"""