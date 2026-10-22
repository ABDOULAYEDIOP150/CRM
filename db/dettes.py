"""
Logique métier des dettes (crédits clients) — indépendante de Streamlit, donc testable.

Principe :
- Une Dette a un montant total, un éventuel acompte et un échéancier (Echeance).
- Les Paiement liés à la dette remboursent les échéances dans l'ordre (la plus ancienne d'abord).
- Une échéance dont la date est passée et qui n'est pas entièrement couverte = RETARD.
"""

import calendar
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote

from .models import Dette, Echeance, Paiement

STATUT_SOLDEE = "Soldée"
STATUT_RETARD = "En retard"
STATUT_A_JOUR = "À jour"
STATUT_ANNULEE = "Annulée"


class ErreurDette(ValueError):
    pass


# ---------- Échéancier ----------


def ajouter_mois(d, n):
    mois = d.month - 1 + n
    annee = d.year + mois // 12
    mois = mois % 12 + 1
    jour = min(d.day, calendar.monthrange(annee, mois)[1])
    return date(annee, mois, jour)


def generer_echeancier(montant, nb_versements, date_premiere, frequence="Mensuelle"):
    """Découpe `montant` en `nb_versements` échéances (montants entiers en FCFA, le dernier absorbe l'arrondi)."""
    from config import FREQUENCES

    montant = round(montant)
    nb_versements = max(int(nb_versements), 1)
    if montant <= 0:
        return []
    regle = FREQUENCES.get(frequence, {"mois": 1})
    base = montant // nb_versements
    lignes = []
    for i in range(nb_versements):
        if "mois" in regle:
            d = ajouter_mois(date_premiere, i * regle["mois"])
        else:
            d = date_premiere + timedelta(days=i * regle["jours"])
        m = base if i < nb_versements - 1 else montant - base * (nb_versements - 1)
        lignes.append((d, float(m)))
    return lignes


# ---------- Création / paiements ----------


def creer_dette(
    session,
    client_id,
    montant,
    nb_versements=1,
    date_premiere=None,
    frequence="Mensuelle",
    acompte=0,
    mode_acompte="Espèces",
    vente_id=None,
    description="",
    date_creation=None,
):
    montant = round(float(montant))
    acompte = round(float(acompte or 0))
    if montant <= 0:
        raise ErreurDette("Le montant de la dette doit être positif.")
    if acompte < 0 or acompte >= montant:
        raise ErreurDette("L'acompte doit être positif et inférieur au montant total.")
    date_creation = date_creation or datetime.now()
    date_premiere = date_premiere or ajouter_mois(date_creation.date(), 1)

    dette = Dette(
        client_id=client_id,
        vente_id=vente_id,
        montant=montant,
        acompte=acompte,
        regle_avant_echeancier=acompte,
        frequence=frequence,
        description=description,
        date_creation=date_creation,
    )
    session.add(dette)
    session.flush()
    for i, (d, m) in enumerate(generer_echeancier(montant - acompte, nb_versements, date_premiere, frequence), 1):
        session.add(Echeance(dette_id=dette.id, numero=i, date_prevue=d, montant_prevu=m))
    if acompte > 0:
        session.add(
            Paiement(
                client_id=client_id,
                dette_id=dette.id,
                vente_id=vente_id,
                montant=acompte,
                mode=mode_acompte,
                note="Acompte",
                date=date_creation,
            )
        )
    session.flush()
    session.refresh(dette)
    return dette


def enregistrer_paiement(session, dette, montant, mode="Espèces", note="", date_paiement=None):
    montant = round(float(montant))
    if dette.statut == "annulee":
        raise ErreurDette("Cette dette est annulée.")
    if montant <= 0:
        raise ErreurDette("Le montant doit être positif.")
    if montant > dette.reste:
        raise ErreurDette(f"Le montant dépasse le reste à payer ({round(dette.reste)}).")
    p = Paiement(
        client_id=dette.client_id,
        dette_id=dette.id,
        vente_id=dette.vente_id,
        montant=montant,
        mode=mode,
        note=note,
        date=date_paiement or datetime.now(),
    )
    session.add(p)
    session.flush()
    session.refresh(dette)
    if dette.reste <= 0:
        dette.statut = "soldee"
        dette.date_solde = p.date
    session.flush()
    return p


def reechelonner(session, dette, nb_versements, date_premiere, frequence="Mensuelle"):
    """Recrée l'échéancier pour le reste à payer (ex. le client demande plus de temps)."""
    if dette.reste <= 0:
        raise ErreurDette("Cette dette est déjà soldée.")
    reste = dette.reste
    dette.echeances.clear()
    session.flush()
    dette.regle_avant_echeancier = dette.total_paye
    dette.frequence = frequence
    for i, (d, m) in enumerate(generer_echeancier(reste, nb_versements, date_premiere, frequence), 1):
        dette.echeances.append(Echeance(numero=i, date_prevue=d, montant_prevu=m))
    session.flush()
    return dette


def annuler_dette(session, dette):
    dette.statut = "annulee"
    session.flush()


# ---------- Analyse ----------


def _today(aujourdhui):
    if aujourdhui is None:
        return date.today()
    return aujourdhui.date() if isinstance(aujourdhui, datetime) else aujourdhui


def etat_echeances(dette, aujourdhui=None):
    """Pour chaque échéance : montant couvert par les paiements, statut et jours de retard."""
    today = _today(aujourdhui)
    disponible = max(dette.total_paye - (dette.regle_avant_echeancier or 0), 0)
    lignes = []
    for e in dette.echeances:
        couvert = min(disponible, e.montant_prevu)
        disponible -= couvert
        reste = e.montant_prevu - couvert
        if reste <= 0:
            statut = "Payée"
        elif e.date_prevue < today:
            statut = "En retard"
        elif couvert > 0:
            statut = "Partielle"
        else:
            statut = "À venir"
        lignes.append(
            {
                "numero": e.numero,
                "date": e.date_prevue,
                "montant": e.montant_prevu,
                "couvert": couvert,
                "reste": reste,
                "statut": statut,
                "jours_retard": (today - e.date_prevue).days if statut == "En retard" else 0,
            }
        )
    return lignes


def situation_dette(dette, aujourdhui=None):
    """Résumé : statut global, montant en retard, jours de retard, prochaine échéance."""
    if dette.statut == "annulee":
        return {
            "statut": STATUT_ANNULEE,
            "montant_retard": 0,
            "jours_retard": 0,
            "prochaine_date": None,
            "prochain_montant": 0,
        }
    lignes = etat_echeances(dette, aujourdhui)
    retards = [l for l in lignes if l["statut"] == "En retard"]
    a_payer = [l for l in lignes if l["reste"] > 0]
    if dette.reste <= 0:
        statut = STATUT_SOLDEE
    elif retards:
        statut = STATUT_RETARD
    else:
        statut = STATUT_A_JOUR
    return {
        "statut": statut,
        "montant_retard": sum(l["reste"] for l in retards),
        "jours_retard": max((l["jours_retard"] for l in retards), default=0),
        "prochaine_date": a_payer[0]["date"] if a_payer else None,
        "prochain_montant": a_payer[0]["reste"] if a_payer else 0,
    }


def dettes_actives(session):
    return session.query(Dette).filter(Dette.statut == "en_cours").all()


def encours_client(session, client_id):
    return sum(d.reste for d in session.query(Dette).filter_by(client_id=client_id, statut="en_cours"))


def client_en_retard(session, client_id, aujourdhui=None):
    return any(
        situation_dette(d, aujourdhui)["statut"] == STATUT_RETARD
        for d in session.query(Dette).filter_by(client_id=client_id, statut="en_cours")
    )


def resume_creances(session, aujourdhui=None, jours_alerte=3):
    """Indicateurs pour le tableau de bord."""
    today = _today(aujourdhui)
    limite = today + timedelta(days=jours_alerte)
    total_du, montant_retard = 0, 0
    retards, proches, par_client = [], [], {}
    for d in dettes_actives(session):
        s = situation_dette(d, today)
        total_du += d.reste
        par_client[d.client] = par_client.get(d.client, 0) + d.reste
        if s["statut"] == STATUT_RETARD:
            montant_retard += s["montant_retard"]
            retards.append((d, s))
        elif s["prochaine_date"] and s["prochaine_date"] <= limite:
            proches.append((d, s))
    retards.sort(key=lambda x: -x[1]["jours_retard"])
    proches.sort(key=lambda x: x[1]["prochaine_date"])
    top = sorted(par_client.items(), key=lambda x: -x[1])
    return {
        "total_du": total_du,
        "nb_debiteurs": len(par_client),
        "montant_retard": montant_retard,
        "retards": retards,
        "echeances_proches": proches,
        "top_debiteurs": top,
    }


# ---------- Relance WhatsApp ----------


def normaliser_telephone(tel, indicatif="221"):
    chiffres = re.sub(r"\D", "", tel or "")
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    if len(chiffres) == 9:  # numéro sénégalais local : 77 123 45 67
        chiffres = indicatif + chiffres
    return chiffres


def lien_whatsapp(tel, message):
    num = normaliser_telephone(tel)
    return f"https://wa.me/{num}?text={quote(message)}" if num else None


def message_relance(modele, client, reste, prochaine_date, boutique, telephone, fmt_money):
    try:
        return modele.format(
            client=client.nom,
            reste=fmt_money(reste),
            echeance=prochaine_date.strftime("%d/%m/%Y") if prochaine_date else "—",
            boutique=boutique,
            telephone=telephone,
        )
    except (KeyError, IndexError):
        return modele
