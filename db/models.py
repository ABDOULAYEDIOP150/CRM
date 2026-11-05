import os
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()


def _url_par_defaut():
    """Ordre de priorité : variable d'environnement CRM_DB_URL > secret Streamlit [database] url > SQLite local.

    Sur Streamlit Cloud, le disque est effacé à chaque redémarrage : pour garder les données en production,
    renseigner une base PostgreSQL (Neon, Supabase…) dans les secrets.
    """
    url = os.environ.get("CRM_DB_URL")
    if not url:
        try:
            import streamlit as st

            url = st.secrets.get("database", {}).get("url")
        except Exception:  # pas de secrets.toml : cas normal en local
            url = None
    return normaliser_url(url or "sqlite:///crm.db")


def normaliser_url(url):
    """Force le pilote PostgreSQL psycopg (v3), quel que soit le format copié chez l'hébergeur.

    « postgres://… » (Heroku, Supabase) et « postgresql://… » (Neon) deviennent « postgresql+psycopg://… ».
    Sans cela, selon la version de SQLAlchemy, il chercherait psycopg2 ou psycopg et l'app plante au démarrage.
    """
    url = url.strip().strip('"').strip("'")
    for prefixe in ("postgres://", "postgresql://"):
        if url.startswith(prefixe):
            return "postgresql+psycopg://" + url[len(prefixe) :]
    return url


DB_URL = _url_par_defaut()


# lazy="selectin" sur les liens les plus parcourus : SQLAlchemy charge par exemple les paiements de
# TOUTES les dettes affichées en une seule requête, au lieu d'une requête par dette. Avec une base en
# ligne (Neon), chaque requête est un aller-retour sur internet : c'est ce qui rendait l'app lente.


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    nom = Column(String)
    telephone = Column(String)
    email = Column(String)
    adresse = Column(String, default="")
    plafond_credit = Column(Float, default=0)  # 0 = pas de plafond
    notes = Column(Text, default="")
    date_creation = Column(DateTime, default=datetime.now)
    ventes = relationship("Vente", back_populates="client")
    dettes = relationship("Dette", back_populates="client")


class Produit(Base):
    __tablename__ = "produits"
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True)
    prix = Column(Float)  # prix de vente
    prix_achat = Column(Float, default=0)  # pour calculer la marge
    stock = Column(Integer)
    categorie = Column(String, default="Divers")
    unite = Column(String, default="pièce")  # sac, kg, barre, mètre, litre…
    seuil_alerte = Column(Integer, nullable=True)  # vide = seuil général des paramètres
    reference = Column(String, default="")  # code court du produit (ex. SAB-001), unique
    ventes_assoc = relationship("VenteProduit", back_populates="produit")
    lots = relationship("LotStock", back_populates="produit", order_by="LotStock.date, LotStock.id", lazy="selectin")

    def seuil(self, defaut):
        return self.seuil_alerte if self.seuil_alerte is not None else defaut


class Vente(Base):
    __tablename__ = "ventes"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    date = Column(DateTime, default=datetime.now)
    mode_livraison = Column(String)
    mode_paiement = Column(String, default="Espèces")
    remise = Column(Float, default=0)
    client = relationship("Client", back_populates="ventes", lazy="selectin")
    produits = relationship("VenteProduit", back_populates="vente", cascade="all, delete-orphan", lazy="selectin")
    dette = relationship("Dette", back_populates="vente", uselist=False, lazy="selectin")
    paiements = relationship("Paiement", back_populates="vente")

    @property
    def sous_total(self):
        return sum(vp.quantite * vp.prix_unit for vp in self.produits)

    @property
    def total(self):
        return max(self.sous_total - (self.remise or 0), 0)


class VenteProduit(Base):
    __tablename__ = "vente_produits"
    id = Column(Integer, primary_key=True)
    vente_id = Column(Integer, ForeignKey("ventes.id"))
    produit_id = Column(Integer, ForeignKey("produits.id"))
    quantite = Column(Integer, default=1)
    prix_unit = Column(Float, default=0.0)
    cout = Column(Float, nullable=True)  # coût d'achat réel de la ligne (lots consommés), pour le bénéfice exact
    vente = relationship("Vente", back_populates="produits")
    produit = relationship("Produit", back_populates="ventes_assoc", lazy="selectin")


class HistoriqueVente(Base):
    __tablename__ = "historique_ventes"
    id = Column(Integer, primary_key=True)
    vente_id = Column(Integer)
    client_nom = Column(String)
    client_telephone = Column(String)
    produit_nom = Column(String)
    quantite = Column(Integer)
    prix_unit = Column(Float)
    date = Column(DateTime)


# ========== NOUVEAU : gestion des dettes ==========


class Dette(Base):
    """Une dette = un montant dû par un client (vente à crédit ou dette saisie manuellement)."""

    __tablename__ = "dettes"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    vente_id = Column(Integer, ForeignKey("ventes.id"), nullable=True)
    montant = Column(Float, nullable=False)  # montant total dû au départ
    acompte = Column(Float, default=0)  # versé le jour de la création
    # Montant déjà réglé quand l'échéancier actuel a été créé (acompte, ou paiements avant un rééchelonnement)
    regle_avant_echeancier = Column(Float, default=0)
    frequence = Column(String, default="Mensuelle")
    description = Column(String, default="")
    statut = Column(String, default="en_cours")  # en_cours | soldee | annulee
    date_creation = Column(DateTime, default=datetime.now)
    date_solde = Column(DateTime, nullable=True)

    client = relationship("Client", back_populates="dettes", lazy="selectin")
    vente = relationship("Vente", back_populates="dette")
    echeances = relationship(
        "Echeance", back_populates="dette", cascade="all, delete-orphan", order_by="Echeance.numero", lazy="selectin"
    )
    paiements = relationship("Paiement", back_populates="dette", order_by="Paiement.date", lazy="selectin")

    @property
    def total_paye(self):
        return sum(p.montant for p in self.paiements)

    @property
    def reste(self):
        return max(self.montant - self.total_paye, 0)

    @property
    def date_echeance_finale(self):
        return self.echeances[-1].date_prevue if self.echeances else None


class Echeance(Base):
    """Une échéance prévue du plan de remboursement."""

    __tablename__ = "echeances"
    id = Column(Integer, primary_key=True)
    dette_id = Column(Integer, ForeignKey("dettes.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    date_prevue = Column(Date, nullable=False)
    montant_prevu = Column(Float, nullable=False)
    dette = relationship("Dette", back_populates="echeances")


class Paiement(Base):
    """Tout encaissement : paiement comptant d'une vente, acompte ou remboursement de dette."""

    __tablename__ = "paiements"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    dette_id = Column(Integer, ForeignKey("dettes.id"), nullable=True)
    vente_id = Column(Integer, ForeignKey("ventes.id"), nullable=True)
    montant = Column(Float, nullable=False)
    mode = Column(String, default="Espèces")
    note = Column(String, default="")
    date = Column(DateTime, default=datetime.now)

    client = relationship("Client")
    dette = relationship("Dette", back_populates="paiements")
    vente = relationship("Vente", back_populates="paiements")


class LotStock(Base):
    """Une entrée de stock = un achat précis : quantité, prix d'achat, prix de vente fixé, fournisseur.

    Le stock d'un produit est la somme des quantités restantes de ses lots. Les ventes consomment
    d'abord les lots les plus anciens (premier entré, premier sorti), ce qui donne le bénéfice exact.
    """

    __tablename__ = "lots_stock"
    id = Column(Integer, primary_key=True)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    date = Column(DateTime, default=datetime.now)
    quantite = Column(Integer, nullable=False)  # quantité achetée
    restant = Column(Integer, nullable=False)  # quantité encore en stock
    prix_achat = Column(Float, nullable=False)  # prix d'achat unitaire
    prix_vente = Column(Float, nullable=True)  # prix de vente décidé à l'entrée
    fournisseur = Column(String, default="")
    note = Column(String, default="")
    produit = relationship("Produit", back_populates="lots")


class MouvementStock(Base):
    """Journal de chaque entrée / sortie de stock : on sait toujours pourquoi un stock a changé."""

    __tablename__ = "mouvements_stock"
    id = Column(Integer, primary_key=True)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    date = Column(DateTime, default=datetime.now)
    type = Column(String, nullable=False)  # Vente | Réception | Correction | Import | Création
    quantite = Column(Integer, nullable=False)  # + entrée, - sortie
    stock_apres = Column(Integer)
    note = Column(String, default="")
    produit = relationship("Produit")


class Parametre(Base):
    __tablename__ = "parametres"
    cle = Column(String, primary_key=True)
    valeur = Column(Text)


# ========== Moteur & sessions ==========
_ENGINES = {}

# ---------- Version des données (pour la mémoire des calculs) ----------
# Chaque enregistrement en base (commit) fait avancer ce compteur. Les calculs coûteux affichés à chaque
# clic (paramètres, alertes du menu…) sont gardés tant que le compteur n'a pas bougé : un clic qui ne
# change rien ne refait aucune requête. L'application tourne dans un seul processus, le compteur est
# donc commun à tous les utilisateurs connectés.
_VERSION = [0]


@event.listens_for(Session, "after_commit")
def _donnees_modifiees(session):
    _VERSION[0] += 1


def version_donnees():
    return _VERSION[0]


def memoire(cle, calcul, taille=32):
    """Résultat de calcul() gardé pour (cle, version des données, base). Recalculé dès qu'un commit a eu lieu."""
    k = (cle, _VERSION[0], DB_URL)
    if k not in _MEMOIRE:
        if len(_MEMOIRE) >= taille:
            _MEMOIRE.clear()
        _MEMOIRE[k] = calcul()
    return _MEMOIRE[k]


_MEMOIRE = {}


def _migrer(engine):
    """Ajoute les colonnes manquantes aux tables existantes (bases créées avec l'ancienne version)."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existantes = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existantes:
                    continue
                type_sql = col.type.compile(engine.dialect)
                defaut = ""
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    val = col.default.arg
                    defaut = f" DEFAULT '{val}'" if isinstance(val, str) else f" DEFAULT {val}"
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {type_sql}{defaut}"))


def init_db(url=None):
    url = normaliser_url(url or DB_URL)
    if url not in _ENGINES:
        engine = create_engine(url, echo=False, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        _migrer(engine)
        _ENGINES[url] = engine
        from .stock import synchroniser_lots  # import local : stock.py importe ce module

        with sessionmaker(bind=engine)() as s:
            synchroniser_lots(s)
            s.commit()
    return _ENGINES[url]


def en_parallele(taches, url=None, max_simultanees=6):
    """Exécute des lectures indépendantes en même temps : {nom: fonction(session)} -> {nom: résultat}.

    Avec une base en ligne, chaque requête attend un aller-retour réseau ; lancer les blocs d'un écran
    en parallèle (une connexion chacun) ramène l'attente à celle du bloc le plus long.
    Réservé à la lecture : chaque bloc a sa propre session, rien n'y est enregistré.
    """
    from concurrent.futures import ThreadPoolExecutor

    init_db(url)  # moteur prêt avant de lancer les fils

    def lancer(fonction):
        with get_session(url) as s:
            return fonction(s)

    with ThreadPoolExecutor(max_workers=min(max_simultanees, len(taches))) as ex:
        futurs = {nom: ex.submit(lancer, f) for nom, f in taches.items()}
        return {nom: f.result() for nom, f in futurs.items()}


def get_session(url=None):
    """Nouvelle session à chaque appel (le moteur est partagé)."""
    Session = sessionmaker(bind=init_db(url), expire_on_commit=False)
    return Session()
