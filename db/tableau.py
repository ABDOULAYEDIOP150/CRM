"""Indicateurs du tableau de bord (calculs purs, testables)."""

from collections import defaultdict
from datetime import date, datetime, timedelta

from config import CLIENT_PASSAGE

from . import dettes as D
from .models import Client, Paiement, Produit, Vente


def _bornes(jour):
    return datetime.combine(jour, datetime.min.time()), datetime.combine(jour, datetime.max.time())


def resume_ventes(session, debut, fin):
    """CA, bénéfice, encaissé, nombre de ventes, panier moyen, part à crédit, répartition par catégorie."""
    ventes = session.query(Vente).filter(Vente.date.between(debut, fin)).all()
    ca = sum(v.total for v in ventes)
    benefice, marge_connue = 0.0, True
    par_categorie, par_produit = defaultdict(float), defaultdict(lambda: [0, 0.0])
    for v in ventes:
        part_remise = (v.remise or 0) / v.sous_total if v.sous_total else 0
        for vp in v.produits:
            montant = vp.prix_unit * vp.quantite * (1 - part_remise)
            p = vp.produit
            par_categorie[(p.categorie if p else None) or "Divers"] += montant
            if p:
                par_produit[p.nom][0] += vp.quantite
                par_produit[p.nom][1] += montant
            if p and p.prix_achat:
                benefice += montant - p.prix_achat * vp.quantite
            else:
                marge_connue = False
    paiements = session.query(Paiement).filter(Paiement.date.between(debut, fin)).all()
    par_mode = defaultdict(float)
    for p in paiements:
        par_mode[p.mode or "Espèces"] += p.montant
    return {
        "ca": ca,
        "nb_ventes": len(ventes),
        "panier_moyen": ca / len(ventes) if ventes else 0,
        "benefice": benefice,
        "marge_complete": marge_connue,
        "encaisse": sum(par_mode.values()),
        "par_mode": dict(sorted(par_mode.items(), key=lambda x: -x[1])),
        "credit": sum(v.total for v in ventes if v.dette),
        "par_categorie": dict(sorted(par_categorie.items(), key=lambda x: -x[1])),
        "par_produit": sorted(((k, q, m) for k, (q, m) in par_produit.items()), key=lambda x: -x[2]),
        "clients": len({v.client_id for v in ventes}),
    }


def jour(session, jour_=None):
    jour_ = jour_ or date.today()
    return resume_ventes(session, *_bornes(jour_))


def variation(actuel, precedent):
    """Évolution en % (None si pas de référence)."""
    if not precedent:
        return None
    return (actuel - precedent) / precedent * 100


def resume_dettes(session, aujourdhui=None, horizon=7):
    today = aujourdhui or date.today()
    tranches = {"À jour": 0.0, "1 à 30 j de retard": 0.0, "31 à 60 j": 0.0, "Plus de 60 j": 0.0}
    a_venir = 0.0
    for d in D.dettes_actives(session):
        s = D.situation_dette(d, today)
        j = s["jours_retard"]
        cle = "À jour" if j == 0 else "1 à 30 j de retard" if j <= 30 else "31 à 60 j" if j <= 60 else "Plus de 60 j"
        tranches[cle] += d.reste
        for l in D.etat_echeances(d, today):
            if l["reste"] > 0 and today <= l["date"] <= today + timedelta(days=horizon):
                a_venir += l["reste"]
    debut_mois = datetime.combine(today.replace(day=1), datetime.min.time())
    recouvre = sum(
        p.montant for p in session.query(Paiement).filter(Paiement.dette_id.isnot(None), Paiement.date >= debut_mois)
    )
    return {"tranches": tranches, "a_encaisser_semaine": a_venir, "recouvre_mois": recouvre}


def resume_stock(session, seuil_defaut):
    produits = session.query(Produit).all()
    return {
        "nb_produits": len(produits),
        "valeur_achat": sum((p.prix_achat or 0) * max(p.stock or 0, 0) for p in produits),
        "valeur_vente": sum((p.prix or 0) * max(p.stock or 0, 0) for p in produits),
        "ruptures": [p for p in produits if (p.stock or 0) <= 0],
        "faibles": sorted((p for p in produits if 0 < (p.stock or 0) <= p.seuil(seuil_defaut)), key=lambda p: p.stock),
        "par_categorie": _stock_par_categorie(produits),
    }


def _stock_par_categorie(produits):
    res = defaultdict(float)
    for p in produits:
        res[p.categorie or "Divers"] += (p.prix_achat or p.prix or 0) * max(p.stock or 0, 0)
    return dict(sorted(res.items(), key=lambda x: -x[1]))


def top_clients(session, debut, fin, n=5):
    totaux = defaultdict(float)
    for v in session.query(Vente).filter(Vente.date.between(debut, fin)):
        if v.client and v.client.nom != CLIENT_PASSAGE:
            totaux[v.client.nom] += v.total
    return sorted(totaux.items(), key=lambda x: -x[1])[:n]


def nouveaux_clients(session, debut, fin):
    return session.query(Client).filter(Client.date_creation.between(debut, fin)).count()
