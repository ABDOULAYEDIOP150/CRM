from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func

import config

from .models import Paiement, Parametre, Produit, Vente, VenteProduit, get_session

# ---------- Paramètres boutique ----------


def get_params():
    with get_session() as s:
        stockes = {p.cle: p.valeur for p in s.query(Parametre).all()}
    return {**config.PARAMETRES_DEFAUT, **stockes}


def get_param(cle):
    return get_params().get(cle)


def set_params(valeurs: dict):
    with get_session() as s:
        for cle, val in valeurs.items():
            s.merge(Parametre(cle=cle, valeur=str(val)))
        s.commit()


# ---------- Statistiques ----------


def get_stats_periode(debut, fin):
    with get_session() as s:
        ventes = s.query(Vente).filter(Vente.date.between(debut, fin)).all()
        encaisse = (
            s.query(func.coalesce(func.sum(Paiement.montant), 0)).filter(Paiement.date.between(debut, fin)).scalar()
        )
        marge = 0
        for v in ventes:
            for vp in v.produits:
                pa = (vp.produit.prix_achat or 0) if vp.produit else 0
                if pa:
                    marge += (vp.prix_unit - pa) * vp.quantite
        return {
            "nb_ventes": len(ventes),
            "ca_total": sum(v.total for v in ventes),
            "nb_produits": sum(vp.quantite for v in ventes for vp in v.produits),
            "nb_clients": len({v.client_id for v in ventes}),
            "encaisse": encaisse or 0,
            "marge": marge,
        }


def get_top_produits(limite=10, debut=None, fin=None):
    with get_session() as s:
        q = (
            s.query(
                Produit.nom,
                func.sum(VenteProduit.quantite).label("total_quantite"),
                func.sum(VenteProduit.quantite * VenteProduit.prix_unit).label("ca_total"),
            )
            .join(VenteProduit)
            .join(Vente)
        )
        if debut and fin:
            q = q.filter(Vente.date.between(debut, fin))
        res = q.group_by(Produit.nom).order_by(func.sum(VenteProduit.quantite).desc()).limit(limite).all()
    return pd.DataFrame(res, columns=["Produit", "Quantite_vendue", "CA_total"])


def get_evolution_ca(jours=30):
    """CA (ventes) et encaissements (argent réellement reçu) par jour."""
    fin = datetime.now()
    debut = (fin - timedelta(days=jours - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    jours_liste = [(debut + timedelta(days=i)).date() for i in range(jours)]
    ca = dict.fromkeys(jours_liste, 0)
    enc = dict.fromkeys(jours_liste, 0)
    with get_session() as s:
        for v in s.query(Vente).filter(Vente.date.between(debut, fin)):
            ca[v.date.date()] = ca.get(v.date.date(), 0) + v.total
        for p in s.query(Paiement).filter(Paiement.date.between(debut, fin)):
            enc[p.date.date()] = enc.get(p.date.date(), 0) + p.montant
    return pd.DataFrame(
        {"Date": jours_liste, "CA": [ca[d] for d in jours_liste], "Encaissé": [enc[d] for d in jours_liste]}
    )


def get_repartition_modes_livraison(debut=None, fin=None):
    with get_session() as s:
        q = s.query(Vente.mode_livraison, func.count(Vente.id))
        if debut and fin:
            q = q.filter(Vente.date.between(debut, fin))
        res = q.group_by(Vente.mode_livraison).all()
    return pd.DataFrame(res, columns=["Mode", "Nombre"])


def get_repartition_paiements(debut=None, fin=None):
    with get_session() as s:
        q = s.query(Paiement.mode, func.sum(Paiement.montant))
        if debut and fin:
            q = q.filter(Paiement.date.between(debut, fin))
        res = q.group_by(Paiement.mode).all()
    return pd.DataFrame(res, columns=["Mode", "Montant"])


def client_de_passage(session):
    """Client générique pour les ventes comptant sans fiche client (créé au premier usage)."""
    from .models import Client

    c = session.query(Client).filter_by(nom=config.CLIENT_PASSAGE).first()
    if c is None:
        c = Client(nom=config.CLIENT_PASSAGE, telephone="")
        session.add(c)
        session.flush()
    return c
