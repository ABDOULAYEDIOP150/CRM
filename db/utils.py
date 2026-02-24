from datetime import datetime, timedelta
from sqlalchemy import func
from .models import get_session, Vente, Produit, VenteProduit, Client
import pandas as pd

session = get_session()

def get_stats_periode(debut, fin):
    """Récupère les statistiques pour une période donnée"""
    ventes_periode = session.query(Vente).filter(Vente.date.between(debut, fin)).all()
    
    nb_ventes = len(ventes_periode)
    ca_total = sum([sum([vp.quantite * vp.prix_unit for vp in v.produits]) for v in ventes_periode])
    nb_produits_vendus = sum([sum([vp.quantite for vp in v.produits]) for v in ventes_periode])
    nb_clients_unis = len(set([v.client_id for v in ventes_periode]))
    
    return {
        "nb_ventes": nb_ventes,
        "ca_total": ca_total,
        "nb_produits": nb_produits_vendus,
        "nb_clients": nb_clients_unis
    }

def get_top_produits(limite=10, debut=None, fin=None):
    """Récupère le top N des produits les plus vendus"""
    query = session.query(
        Produit.nom,
        func.sum(VenteProduit.quantite).label('total_quantite'),
        func.sum(VenteProduit.quantite * VenteProduit.prix_unit).label('ca_total')
    ).join(VenteProduit).join(Vente)
    
    if debut and fin:
        query = query.filter(Vente.date.between(debut, fin))
    
    result = query.group_by(Produit.nom).order_by(func.sum(VenteProduit.quantite).desc()).limit(limite).all()
    
    return pd.DataFrame(result, columns=['Produit', 'Quantite_vendue', 'CA_total'])

def get_evolution_ca(jours=30):
    """Récupère l'évolution du CA sur les X derniers jours"""
    fin = datetime.now()
    debut = fin - timedelta(days=jours)
    
    ventes = session.query(Vente).filter(Vente.date.between(debut, fin)).all()
    
    ca_par_jour = {}
    for i in range(jours):
        date_jour = (debut + timedelta(days=i)).date()
        ca_par_jour[date_jour] = 0
    
    for vente in ventes:
        date_vente = vente.date.date()
        ca = sum([vp.quantite * vp.prix_unit for vp in vente.produits])
        ca_par_jour[date_vente] = ca_par_jour.get(date_vente, 0) + ca
    
    df = pd.DataFrame(list(ca_par_jour.items()), columns=['Date', 'CA'])
    return df

def get_repartition_modes_livraison(debut=None, fin=None):
    """Récupère la répartition des modes de livraison"""
    query = session.query(Vente.mode_livraison, func.count(Vente.id))
    if debut and fin:
        query = query.filter(Vente.date.between(debut, fin))
    result = query.group_by(Vente.mode_livraison).all()
    
    return pd.DataFrame(result, columns=['Mode', 'Nombre'])
