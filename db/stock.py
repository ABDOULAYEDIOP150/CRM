"""Toutes les modifications de stock passent par ici pour être tracées dans le journal."""

from datetime import datetime

from .models import MouvementStock


def mouvement(session, produit, quantite, type_, note="", date=None):
    """Ajoute `quantite` (négative pour une sortie) au stock du produit et l'enregistre dans le journal."""
    quantite = int(quantite)
    if quantite == 0:
        return None
    produit.stock = (produit.stock or 0) + quantite
    m = MouvementStock(produit=produit, quantite=quantite, type=type_, stock_apres=produit.stock, note=note,
                       date=date or datetime.now())  # fmt: skip
    session.add(m)
    return m


def fixer_stock(session, produit, nouveau, type_="Correction", note=""):
    """Met le stock à une valeur précise (inventaire, correction) en journalisant l'écart."""
    return mouvement(session, produit, int(nouveau) - (produit.stock or 0), type_, note)
