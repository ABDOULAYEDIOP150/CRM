"""Stock géré par lots d'achat (entrées de stock).

- Le **catalogue** (table produits) décrit le produit : code, nom, catégorie, unité.
- Une **entrée de stock** (LotStock) = un achat : quantité, prix d'achat, prix de vente, fournisseur.
- Le stock d'un produit = somme des quantités restantes de ses lots (copiée dans produits.stock).
- Une vente consomme les lots les plus anciens d'abord (FIFO) : on connaît le coût réel, donc le bénéfice exact.
- Chaque mouvement est tracé dans le journal (mouvements_stock).
"""

import re
import unicodedata
from datetime import datetime

from .models import LotStock, MouvementStock, Produit


class ErreurStock(ValueError):
    pass


# ------------------------------------------------------------------ Code produit
def _lettres(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", t)


def generer_code(session, nom):
    """« Sable fin » -> SAB-001 (puis SAB-002…). Court, unique, facile à taper."""
    prefixe = (_lettres(nom) + "XXX")[:3]
    existants = {p.reference for p in session.query(Produit.reference).filter(Produit.reference.like(f"{prefixe}-%"))}
    n = 1
    while f"{prefixe}-{n:03d}" in existants:
        n += 1
    return f"{prefixe}-{n:03d}"


# ------------------------------------------------------------------ Calculs
def recalculer(produit):
    """Met à jour le stock total et le prix d'achat moyen (pondéré) à partir des lots restants."""
    restants = [l for l in produit.lots if l.restant > 0]
    produit.stock = sum(l.restant for l in restants)
    if produit.stock:
        produit.prix_achat = round(sum(l.restant * l.prix_achat for l in restants) / produit.stock)
    return produit


def marge(prix_achat, prix_vente):
    """(bénéfice par unité, taux de marge sur le prix de vente)."""
    if not prix_vente:
        return 0, 0.0
    return prix_vente - prix_achat, (prix_vente - prix_achat) / prix_vente


def _reprendre(session, produit):
    """Si le produit a du stock non rattaché à un lot (ancienne version), crée le lot correspondant."""
    if produit.id is not None:
        session.flush()
        session.refresh(produit)
    ecart = (produit.stock or 0) - sum(l.restant for l in produit.lots)
    if ecart > 0:
        session.add(
            LotStock(
                produit=produit,
                quantite=ecart,
                restant=ecart,
                prix_achat=float(produit.prix_achat or 0),
                prix_vente=produit.prix,
                note="Stock initial (reprise)",
            )
        )
        session.flush()
        session.refresh(produit)


def _journal(session, produit, quantite, type_, note, date):
    session.add(
        MouvementStock(
            produit=produit,
            quantite=quantite,
            type=type_,
            stock_apres=produit.stock,
            note=note,
            date=date or datetime.now(),
        )
    )


# ------------------------------------------------------------------ Entrées / sorties
def entree_stock(
    session, produit, quantite, prix_achat, prix_vente=None, fournisseur="", note="", type_="Réception", date=None
):
    """Enregistre un achat : crée un lot, met à jour le stock, le prix d'achat moyen et le prix de vente."""
    quantite = int(quantite)
    if quantite <= 0:
        raise ErreurStock("La quantité doit être positive.")
    if prix_achat is None or prix_achat < 0:
        raise ErreurStock("Le prix d'achat est obligatoire.")
    _reprendre(session, produit)
    lot = LotStock(
        produit=produit,
        quantite=quantite,
        restant=quantite,
        prix_achat=float(prix_achat),
        prix_vente=float(prix_vente) if prix_vente else None,
        fournisseur=fournisseur or "",
        note=note or "",
        date=date or datetime.now(),
    )
    session.add(lot)
    session.flush()
    session.refresh(produit)
    recalculer(produit)
    if prix_vente:
        produit.prix = float(prix_vente)
    detail = " · ".join(
        x for x in [f"acheté {round(prix_achat)}/u", f"fournisseur {fournisseur}" if fournisseur else "", note] if x
    )
    _journal(session, produit, quantite, type_, detail, date)
    return lot


def sortie_stock(session, produit, quantite, type_="Vente", note="", date=None):
    """Retire `quantite` en consommant les lots les plus anciens. Retourne le coût d'achat total sorti."""
    quantite = int(quantite)
    if quantite <= 0:
        return 0.0
    _reprendre(session, produit)
    if quantite > (produit.stock or 0):
        raise ErreurStock(f"Stock insuffisant pour {produit.nom} ({produit.stock} disponible(s)).")
    reste, cout = quantite, 0.0
    for lot in produit.lots:
        if reste == 0:
            break
        pris = min(lot.restant, reste)
        if pris:
            lot.restant -= pris
            cout += pris * lot.prix_achat
            reste -= pris
    recalculer(produit)
    _journal(session, produit, -quantite, type_, note, date)
    return cout


def mouvement(session, produit, quantite, type_, note="", date=None):
    """Compatibilité : + entrée au prix d'achat moyen actuel, - sortie FIFO."""
    if quantite > 0:
        return entree_stock(session, produit, quantite, produit.prix_achat or 0, None, "", note, type_, date)
    if quantite < 0:
        return sortie_stock(session, produit, -quantite, type_, note, date)
    return None


def fixer_stock(session, produit, nouveau, type_="Inventaire", note=""):
    """Inventaire : met le stock à la quantité réellement comptée (écart journalisé)."""
    _reprendre(session, produit)
    return mouvement(session, produit, int(nouveau) - (produit.stock or 0), type_, note)


def synchroniser_lots(session):
    """Migration : un produit qui a du stock mais pas (assez) de lots reçoit un lot « Stock initial »."""
    for p in session.query(Produit).all():
        dans_lots = sum(l.restant for l in p.lots)
        ecart = (p.stock or 0) - dans_lots
        if ecart > 0:
            session.add(
                LotStock(
                    produit=p,
                    quantite=ecart,
                    restant=ecart,
                    prix_achat=float(p.prix_achat or 0),
                    prix_vente=p.prix,
                    note="Stock initial (reprise)",
                )
            )
        if not p.reference:
            session.flush()
            p.reference = generer_code(session, p.nom)
    session.flush()
