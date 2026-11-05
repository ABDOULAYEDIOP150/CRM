"""Indicateurs du tableau de bord (calculs purs, testables)."""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func

from config import CLIENT_PASSAGE

from . import dettes as D
from .models import Client, Dette, Paiement, Produit, Vente, VenteProduit


def _bornes(jour):
    return datetime.combine(jour, datetime.min.time()), datetime.combine(jour, datetime.max.time())


def resume_ventes(session, debut, fin):
    """CA, bénéfice, encaissé, nombre de ventes, panier moyen, part à crédit, répartition par catégorie.

    3 requêtes quel que soit le nombre de ventes : les lignes de vente avec leur produit (sans charger
    lots, dettes ni échéances), les ventes à crédit, les paiements.
    """
    lignes = (
        session.query(
            Vente.id, Vente.client_id, Vente.remise, VenteProduit.quantite, VenteProduit.prix_unit,
            VenteProduit.cout, Produit.nom, Produit.categorie, Produit.prix_achat,
        )
        .select_from(Vente)
        .outerjoin(VenteProduit, VenteProduit.vente_id == Vente.id)
        .outerjoin(Produit, Produit.id == VenteProduit.produit_id)
        .filter(Vente.date.between(debut, fin))
        .all()
    )  # fmt: skip
    ventes = {}  # id -> [client_id, remise, sous_total, lignes]
    for vid, client_id, remise, q, pu, cout, nom, cat, pa in lignes:
        v = ventes.setdefault(vid, [client_id, remise or 0, 0.0, []])
        if q is not None:
            v[2] += q * (pu or 0)
            v[3].append((q, pu or 0, cout, nom, cat, pa))
    totaux = {vid: max(st - remise, 0) for vid, (_, remise, st, _) in ventes.items()}
    ca = sum(totaux.values())
    benefice, marge_connue = 0.0, True
    par_categorie, par_produit = defaultdict(float), defaultdict(lambda: [0, 0.0])
    marge_categorie = defaultdict(float)
    for _, remise, st, lv in ventes.values():
        part_remise = remise / st if st else 0
        for q, pu, cout, nom, cat, pa in lv:
            montant = pu * q * (1 - part_remise)
            categorie = (cat if nom is not None else None) or "Divers"
            par_categorie[categorie] += montant
            if nom is not None:
                par_produit[nom][0] += q
                par_produit[nom][1] += montant
            if cout is not None:  # coût réel des lots vendus
                gain = montant - cout
            elif nom is not None and pa:  # anciennes ventes : prix d'achat moyen
                gain = montant - pa * q
            else:
                gain = None
                marge_connue = False
            if gain is not None:
                benefice += gain
                marge_categorie[categorie] += gain
    a_credit = (
        {i for (i,) in session.query(Dette.vente_id).filter(Dette.vente_id.in_(list(ventes)))} if ventes else set()
    )
    par_mode = defaultdict(float)
    for mode, montant in session.query(Paiement.mode, Paiement.montant).filter(Paiement.date.between(debut, fin)):
        par_mode[mode or "Espèces"] += montant
    return {
        "ca": ca,
        "nb_ventes": len(ventes),
        "panier_moyen": ca / len(ventes) if ventes else 0,
        "benefice": benefice,
        "marge_complete": marge_connue,
        "encaisse": sum(par_mode.values()),
        "par_mode": dict(sorted(par_mode.items(), key=lambda x: -x[1])),
        "credit": sum(t for vid, t in totaux.items() if vid in a_credit),
        "par_categorie": dict(sorted(par_categorie.items(), key=lambda x: -x[1])),
        "marge_par_categorie": dict(sorted(marge_categorie.items(), key=lambda x: -x[1])),
        "par_produit": sorted(((k, q, m) for k, (q, m) in par_produit.items()), key=lambda x: -x[2]),
        "clients": len({v[0] for v in ventes.values()}),
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
        "ruptures": [p for p in produits if (p.stock or 0) <= 0 and p.lots],  # déjà acheté, plus en stock
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
    for client_id, _, total in _totaux_ventes(session, debut, fin):
        totaux[client_id] += total
    noms = dict(session.query(Client.id, Client.nom).filter(Client.id.in_(list(totaux)))) if totaux else {}
    par_nom = defaultdict(float)
    for cid, t in totaux.items():
        if cid in noms and noms[cid] != CLIENT_PASSAGE:
            par_nom[noms[cid]] += t
    return sorted(par_nom.items(), key=lambda x: -x[1])[:n]


def nouveaux_clients(session, debut, fin):
    return session.query(Client).filter(Client.date_creation.between(debut, fin)).count()


def _totaux_ventes(session, debut=None, fin=None, recents=None):
    """[(client_id, date, total)] calculés par la base en UNE requête (sans charger produits, lots, dettes…)."""
    sous_total = func.coalesce(func.sum(VenteProduit.quantite * VenteProduit.prix_unit), 0)
    q = (
        session.query(Vente.client_id, Vente.date, sous_total, Vente.remise)
        .outerjoin(VenteProduit, VenteProduit.vente_id == Vente.id)
        .group_by(Vente.id, Vente.client_id, Vente.date, Vente.remise)
    )
    if debut is not None:
        q = q.filter(Vente.date.between(debut, fin))
    if recents:
        q = q.order_by(Vente.date.desc()).limit(recents)
    return [(c, d, max((st or 0) - (r or 0), 0)) for c, d, st, r in q]


MOIS_COURTS = ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]


def evolution(session, debut, fin):
    """CA par jour (≤ 14 jours), par semaine (≤ 62 jours) ou par mois : [(étiquette, CA), ...], en une requête."""
    nb_jours = (fin - debut).days
    if 14 < nb_jours <= 62:
        return _par_semaine(session, debut, fin)
    par_mois = nb_jours > 62
    totaux = defaultdict(float)
    for _, quand, total in _totaux_ventes(session, debut, fin):
        cle = (quand.year, quand.month) if par_mois else quand.date()
        totaux[cle] += total
    if par_mois:
        cles, (a, m) = [], (debut.year, debut.month)
        while (a, m) <= (fin.year, fin.month):
            cles.append((a, m))
            a, m = (a + 1, 1) if m == 12 else (a, m + 1)
        return [(f"{MOIS_COURTS[m - 1]}", totaux[(a, m)]) for a, m in cles]
    jours = [(debut + timedelta(days=i)).date() for i in range((fin.date() - debut.date()).days + 1)]
    return [(j.strftime("%d/%m"), totaux[j]) for j in jours]


def _par_semaine(session, debut, fin):
    """Tranches de 7 jours qui se terminent aujourd'hui (la dernière est la semaine en cours)."""
    bornes = []
    fin_tranche = fin.date()
    while fin_tranche >= debut.date():
        bornes.append((max(fin_tranche - timedelta(days=6), debut.date()), fin_tranche))
        fin_tranche -= timedelta(days=7)
    bornes.reverse()
    totaux = defaultdict(float)
    for _, quand, total in _totaux_ventes(session, debut, fin):
        for i, (a, b) in enumerate(bornes):
            if a <= quand.date() <= b:
                totaux[i] += total
                break
    return [(f"{a:%d/%m}–{b:%d/%m}", totaux[i]) for i, (a, b) in enumerate(bornes)]


def clients_recents(session, n=5):
    """Derniers clients servis (hors client de passage) : [(client, montant de la dernière vente, date), ...]."""
    vus, lignes = set(), []
    for client_id, quand, total in _totaux_ventes(session, recents=60):
        if client_id is None or client_id in vus:
            continue
        vus.add(client_id)
        lignes.append((client_id, total, quand))
    clients = {c.id: c for c in session.query(Client).filter(Client.id.in_(vus))} if vus else {}
    res = [(clients[i], m, d) for i, m, d in lignes if i in clients and clients[i].nom != CLIENT_PASSAGE]
    return res[:n]
