"""
Package des modules fonctionnels du CRM
Ce package contient tous les modules d'interface utilisateur
"""

# Version du package modules
__version__ = "1.0.0"

# Import conditionnel - éviter d'importer test automatiquement
# On importe seulement les modules nécessaires pour le fonctionnement normal
from . import dashboard
from . import clients
from . import produits
from . import ventes
from . import factures
from . import historique

# NE PAS IMPORTER test ici pour éviter les circular imports
# from . import test  <-- À SUPPRIMER ou commenter

# Fonctions d'affichage pour chaque module
def show_dashboard():
    """Affiche le dashboard principal"""
    from .dashboard import show_dashboard
    return show_dashboard()

def show_clients():
    """Affiche la gestion des clients"""
    from .clients import show_clients
    return show_clients()

def show_produits():
    """Affiche la gestion des produits"""
    from .produits import show_produits
    return show_produits()

def show_ventes():
    """Affiche la gestion des ventes"""
    from .ventes import show_ventes
    return show_ventes()

def show_factures():
    """Affiche la génération de factures"""
    from .factures import show_factures
    return show_factures()

def show_historique():
    """Affiche l'historique des ventes"""
    from .historique import show_historique
    return show_historique()

# Fonction de test - importée uniquement quand nécessaire
def run_tests():
    """Exécute les tests unitaires"""
    from .test import run_tests  # Import local pour éviter la circular import
    return run_tests()

# Dictionnaire des modules pour faciliter le routage
MODULES = {
    "dashboard": {
        "name": "Tableau de bord",
        "icon": "📊",
        "function": show_dashboard,
        "description": "Statistiques et analyse des performances"
    },
    "clients": {
        "name": "Clients",
        "icon": "👥",
        "function": show_clients,
        "description": "Gestion des clients"
    },
    "produits": {
        "name": "Produits",
        "icon": "📦",
        "function": show_produits,
        "description": "Gestion des produits et stock"
    },
    "ventes": {
        "name": "Ventes",
        "icon": "🛒",
        "function": show_ventes,
        "description": "Enregistrement des ventes"
    },
    "factures": {
        "name": "Factures",
        "icon": "📄",
        "function": show_factures,
        "description": "Génération de factures PDF"
    },
    "historique": {
        "name": "Historique",
        "icon": "📊",
        "function": show_historique,
        "description": "Historique des ventes"
    }
}

# Pour faciliter l'accès aux noms des modules
MODULE_NAMES = list(MODULES.keys())
MODULE_TITLES = [m["name"] for m in MODULES.values()]
MODULE_ICONS = [m["icon"] for m in MODULES.values()]

def get_module_info(module_name):
    """Retourne les informations d'un module par son nom"""
    return MODULES.get(module_name, None)

def list_modules():
    """Liste tous les modules disponibles"""
    return [(name, info["name"], info["icon"], info["description"]) 
            for name, info in MODULES.items()]

# Documentation du package
__doc__ = """
Package Modules pour CRM Professionnel
======================================

Ce package contient tous les modules d'interface utilisateur du CRM.

Modules disponibles:
    - dashboard: 📊 Tableau de bord avec statistiques
    - clients: 👥 Gestion des clients
    - produits: 📦 Gestion des produits
    - ventes: 🛒 Enregistrement des ventes
    - factures: 📄 Génération de factures PDF
    - historique: 📊 Historique des ventes

Tests:
    - Pour exécuter les tests: python -m modules.test
"""