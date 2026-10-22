"""Moteur d'alertes : tout ce qui demande une action du commerçant, classé par urgence.

Indépendant de Streamlit (testable). Chaque alerte indique quoi faire et vers quelle page aller.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func

from . import dettes as D
from .models import Client, Dette, Produit, Vente, VenteProduit

CRITIQUE, ATTENTION, INFO = "critique", "attention", "info"
ORDRE = {CRITIQUE: 0, ATTENTION: 1, INFO: 2}

# type -> (icône, libellé de la catégorie)
TYPES = {
    "dette_retard": ("🔴", "Dettes en retard"),
    "echeance_aujourdhui": ("🟠", "Paiements attendus aujourd'hui"),
    "echeance_proche": ("🟡", "Paiements attendus bientôt"),
    "plafond": ("⛔", "Plafond de crédit dépassé"),
    "rupture": ("📦", "Ruptures de stock"),
    "stock_faible": ("📉", "Stock faible"),
    "perte": ("💸", "Vendu en dessous du prix d'achat"),
    "dormant": ("💤", "Stock qui ne se vend pas"),
    "sans_prix_achat": ("❔", "Prix d'achat manquant"),
}


@dataclass
class Alerte:
    type: str
    niveau: str
    titre: str
    detail: str
    montant: float = 0
    action: str = ""  # libellé du bouton
    page: str = ""  # page de l'application où agir
    etat: dict = field(default_factory=dict)  # valeurs à passer à la page (ex. dette_ouverte)
    client: Client | None = None
    produit_id: int | None = None
    dette: Dette | None = None
    tri: float = 0

    @property
    def icone(self):
        return TYPES[self.type][0]


def _today(aujourdhui):
    if aujourdhui is None:
        return date.today()
    return aujourdhui.date() if isinstance(aujourdhui, datetime) else aujourdhui


def derniere_vente_par_produit(session):
    lignes = (
        session.query(VenteProduit.produit_id, func.max(Vente.date))
        .join(Vente, Vente.id == VenteProduit.vente_id)
        .group_by(VenteProduit.produit_id)
        .all()
    )
    return dict(lignes)


def calculer_alertes(session, params, aujourdhui=None):
    today = _today(aujourdhui)
    jours_ech = int(params.get("jours_alerte_echeance", 2))
    seuil_defaut = int(params.get("seuil_stock", 2))
    jours_dormant = int(params.get("jours_stock_dormant", 30))
    alertes = []

    # ---------- Dettes ----------
    encours_client = {}
    for d in D.dettes_actives(session):
        s = D.situation_dette(d, today)
        encours_client[d.client] = encours_client.get(d.client, 0) + d.reste
        nom = d.client.nom
        etat = {"dette_ouverte": d.id}
        if s["statut"] == D.STATUT_RETARD:
            alertes.append(
                Alerte(
                    "dette_retard",
                    CRITIQUE,
                    nom,
                    f"{s['jours_retard']} jour(s) de retard · reste {round(d.reste):,} sur la dette".replace(",", " "),
                    s["montant_retard"],
                    "Encaisser",
                    "Dettes",
                    etat,
                    d.client,
                    dette=d,
                    tri=-s["jours_retard"],
                )
            )
        elif s["prochaine_date"] is not None:
            delai = (s["prochaine_date"] - today).days
            if delai == 0:
                alertes.append(
                    Alerte(
                        "echeance_aujourdhui",
                        ATTENTION,
                        nom,
                        "doit payer aujourd'hui",
                        s["prochain_montant"],
                        "Encaisser",
                        "Dettes",
                        etat,
                        d.client,
                        dette=d,
                    )
                )
            elif 0 < delai <= jours_ech:
                quand = "demain" if delai == 1 else f"dans {delai} jours"
                alertes.append(
                    Alerte(
                        "echeance_proche",
                        ATTENTION,
                        nom,
                        f"doit payer {quand} ({s['prochaine_date'].strftime('%d/%m')})",
                        s["prochain_montant"],
                        "Relancer",
                        "Dettes",
                        etat,
                        d.client,
                        dette=d,
                        tri=delai,
                    )
                )
    for c, encours in encours_client.items():
        if c.plafond_credit and encours > c.plafond_credit:
            alertes.append(
                Alerte(
                    "plafond",
                    ATTENTION,
                    c.nom,
                    f"doit {round(encours):,} pour un plafond de {round(c.plafond_credit):,}".replace(",", " "),
                    encours - c.plafond_credit,
                    "Voir le client",
                    "Clients",
                    {"client_ouvert": c.id},
                    c,
                )
            )

    # ---------- Stock ----------
    dernieres = derniere_vente_par_produit(session)
    limite_dormant = datetime.combine(today - timedelta(days=jours_dormant), datetime.min.time())
    for p in session.query(Produit).order_by(Produit.nom):
        seuil = p.seuil(seuil_defaut)
        unite = p.unite or "pièce"
        if (p.stock or 0) <= 0:
            if not p.lots:  # produit du catalogue jamais acheté : pas une rupture
                continue
            alertes.append(
                Alerte(
                    "rupture",
                    CRITIQUE,
                    p.nom,
                    "plus rien en stock : commander",
                    0,
                    "Commander",
                    "Entrees",
                    {},
                    produit_id=p.id,
                )
            )
        elif p.stock <= seuil:
            alertes.append(
                Alerte(
                    "stock_faible",
                    ATTENTION,
                    p.nom,
                    f"reste {p.stock} {unite}(s) (seuil {seuil})",
                    0,
                    "Commander",
                    "Entrees",
                    {},
                    produit_id=p.id,
                    tri=p.stock,
                )
            )
        if p.prix_achat and p.prix is not None and p.prix < p.prix_achat:
            alertes.append(
                Alerte(
                    "perte",
                    ATTENTION,
                    p.nom,
                    f"prix de vente {round(p.prix)} < prix d'achat {round(p.prix_achat)}",
                    p.prix_achat - p.prix,
                    "Corriger le prix",
                    "Produits",
                    {},
                    produit_id=p.id,
                )
            )
        derniere = dernieres.get(p.id)
        if (p.stock or 0) > 0 and (derniere is None or derniere < limite_dormant):
            depuis = f"pas vendu depuis {(today - derniere.date()).days} jours" if derniere else "jamais vendu"
            alertes.append(
                Alerte(
                    "dormant",
                    INFO,
                    p.nom,
                    f"{depuis} · {p.stock} {unite}(s) immobilisé(s)",
                    (p.prix_achat or p.prix or 0) * p.stock,
                    "Voir",
                    "Produits",
                    {},
                    produit_id=p.id,
                )
            )
        if not p.prix_achat and (p.stock or 0) > 0:
            alertes.append(
                Alerte(
                    "sans_prix_achat",
                    INFO,
                    p.nom,
                    "renseignez le prix d'achat pour connaître la marge",
                    0,
                    "Compléter",
                    "Entrees",
                    {},
                    produit_id=p.id,
                )
            )

    alertes.sort(key=lambda a: (ORDRE[a.niveau], list(TYPES).index(a.type), a.tri))
    return alertes


def compter(alertes):
    return {
        "total": len(alertes),
        CRITIQUE: sum(a.niveau == CRITIQUE for a in alertes),
        ATTENTION: sum(a.niveau == ATTENTION for a in alertes),
        INFO: sum(a.niveau == INFO for a in alertes),
        **{t: sum(a.type == t for a in alertes) for t in TYPES},
    }
