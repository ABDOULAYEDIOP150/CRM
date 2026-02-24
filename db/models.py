from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    nom = Column(String)
    telephone = Column(String)
    email = Column(String)
    date_creation = Column(DateTime, default=datetime.now)  # ✅ Bien présente
    ventes = relationship("Vente", back_populates="client")

class Produit(Base):
    __tablename__ = "produits"
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True)
    prix = Column(Float)
    stock = Column(Integer)
    #date_creation = Column(DateTime, default=datetime.now)  # ✅ Cette ligne DOIT être présente
    ventes_assoc = relationship("VenteProduit", back_populates="produit")

class Vente(Base):
    __tablename__ = "ventes"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    date = Column(DateTime, default=datetime.now)
    mode_livraison = Column(String)
    client = relationship("Client", back_populates="ventes")
    produits = relationship("VenteProduit", back_populates="vente", cascade="all, delete-orphan")

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

# Initialisation de la base de données
def init_db():
    engine = create_engine("sqlite:///crm.db", echo=False)
    Base.metadata.create_all(engine)  # ✅ Crée toutes les tables avec les bonnes colonnes
    return engine

def get_session():
    engine = init_db()
    Session = sessionmaker(bind=engine)
    return Session()