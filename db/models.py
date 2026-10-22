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
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

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
    url = url or "sqlite:///crm.db"
    if url.startswith("postgres://"):  # format donné par certains hébergeurs
        url = "postgresql://" + url[len("postgres://") :]
    return url


DB_URL = _url_par_defaut()


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
    ventes_assoc = relationship("VenteProduit", back_populates="produit")


class Vente(Base):
    __tablename__ = "ventes"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    date = Column(DateTime, default=datetime.now)
    mode_livraison = Column(String)
    mode_paiement = Column(String, default="Espèces")
    remise = Column(Float, default=0)
    client = relationship("Client", back_populates="ventes")
    produits = relationship("VenteProduit", back_populates="vente", cascade="all, delete-orphan")
    dette = relationship("Dette", back_populates="vente", uselist=False)
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
    vente = relationship("Vente", back_populates="produits")
    produit = relationship("Produit", back_populates="ventes_assoc")


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

    client = relationship("Client", back_populates="dettes")
    vente = relationship("Vente", back_populates="dette")
    echeances = relationship(
        "Echeance", back_populates="dette", cascade="all, delete-orphan", order_by="Echeance.numero"
    )
    paiements = relationship("Paiement", back_populates="dette", order_by="Paiement.date")

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


class Parametre(Base):
    __tablename__ = "parametres"
    cle = Column(String, primary_key=True)
    valeur = Column(Text)


# ========== Moteur & sessions ==========
_ENGINES = {}


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
    url = url or DB_URL
    if url not in _ENGINES:
        engine = create_engine(url, echo=False, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        _migrer(engine)
        _ENGINES[url] = engine
    return _ENGINES[url]


def get_session(url=None):
    """Nouvelle session à chaque appel (le moteur est partagé)."""
    Session = sessionmaker(bind=init_db(url), expire_on_commit=False)
    return Session()
