"""
Remplit la base avec des données de démonstration (quincaillerie à Dakar).
Usage :  python demo_data.py        (n'ajoute rien si des clients existent déjà)
"""

import random
from datetime import date, datetime, timedelta

from db import dettes as D
from db.models import Client, HistoriqueVente, Paiement, Produit, Vente, VenteProduit, get_session

CLIENTS = [
    ("Awa Ndiaye", "77 412 33 10", "Parcelles Assainies"),
    ("Moussa Fall", "78 220 45 91", "Médina"),
    ("Fatou Diop", "76 900 12 34", "Grand Yoff"),
    ("Ibrahima Sarr", "70 555 66 77", "Pikine"),
    ("Aminata Ba", "77 300 88 21", "Liberté 6"),
    ("Cheikh Mbaye", "78 111 22 33", "Guédiawaye"),
]
# (nom, prix de vente, prix d'achat, stock, catégorie, unité, seuil d'alerte)
PRODUITS = [
    ("Ciment CPJ 45 - 50 kg", 4600, 4150, 120, "Ciment & maçonnerie", "sac", 20),
    ("Fer à béton 10 mm", 3500, 3000, 60, "Fer & métaux", "barre", 15),
    ("Fer à béton 8 mm", 2300, 1950, 8, "Fer & métaux", "barre", 15),
    ("Tôle ondulée 2 m", 4800, 4000, 40, "Fer & métaux", "pièce", 10),
    ("Clous 70 mm", 1200, 950, 35, "Quincaillerie générale", "kg", 10),
    ("Tuyau PVC 32 mm", 2500, 1900, 50, "Plomberie", "barre", 10),
    ("Robinet laiton", 3500, 2600, 0, "Plomberie", "pièce", 5),
    ("Fil électrique 2,5 mm²", 14000, 11500, 12, "Électricité", "rouleau", 5),
    ("Ampoule LED 12 W", 1000, 700, 60, "Électricité", "pièce", 20),
    ("Peinture à eau blanche 20 L", 22000, 18000, 9, "Peinture", "seau", 4),
    ("Café Touba 250 g", 1000, 800, 40, "Alimentation", "paquet", 10),
    ("Allumettes (paquet de 10)", 250, 180, 100, "Alimentation", "paquet", 20),
    # produits qui ne se vendent pas (stock dormant)
    ("Brouette renforcée", 28000, 23000, 6, "Outillage", "pièce", 2),
    ("Échelle alu 3 m", 45000, 38000, 3, "Outillage", "pièce", 1),
]
NB_VENDUS = 12  # les 2 derniers produits ne sont jamais vendus


def main():
    random.seed(7)
    with get_session() as s:
        if s.query(Client).count():
            print("La base contient déjà des clients : rien à faire.")
            return
        clients = [
            Client(
                nom=n,
                telephone=t,
                adresse=a,
                plafond_credit=random.choice([0, 50000, 100000]),
                date_creation=datetime.now() - timedelta(days=90),
            )
            for n, t, a in CLIENTS
        ]
        produits = [
            Produit(nom=n, prix=p, prix_achat=pa, stock=st, categorie=cat, unite=u, seuil_alerte=se)
            for n, p, pa, st, cat, u, se in PRODUITS
        ]
        s.add_all(clients + produits)
        s.flush()
        for i in range(25):
            jour = datetime.now() - timedelta(days=random.randint(0, 60), hours=random.randint(0, 8))
            c = random.choice(clients)
            v = Vente(client_id=c.id, date=jour, mode_livraison="Retrait en magasin", mode_paiement="Espèces")
            s.add(v)
            s.flush()
            for p in random.sample([x for x in produits[:NB_VENDUS] if x.stock > 5], k=random.randint(1, 3)):
                q = random.randint(1, 3)
                s.add(VenteProduit(vente_id=v.id, produit_id=p.id, quantite=q, prix_unit=p.prix))
                s.add(
                    HistoriqueVente(
                        vente_id=v.id,
                        client_nom=c.nom,
                        client_telephone=c.telephone,
                        produit_nom=p.nom,
                        quantite=q,
                        prix_unit=p.prix,
                        date=jour,
                    )
                )
            s.flush()
            s.refresh(v)
            if i % 4 == 0:  # vente à crédit
                v.mode_paiement = "Crédit"
                d = D.creer_dette(
                    s,
                    c.id,
                    v.total,
                    nb_versements=random.choice([1, 2, 3]),
                    date_premiere=(jour + timedelta(days=random.choice([7, 15, 30]))).date(),
                    frequence="Toutes les 2 semaines",
                    acompte=round(v.total * 0.2, -2),
                    mode_acompte="Wave",
                    vente_id=v.id,
                    description=f"Vente F-{v.id:05d}",
                    date_creation=jour,
                )
                if random.random() < 0.5 and d.reste > 0:
                    D.enregistrer_paiement(
                        s, d, round(d.reste / 2), "Orange Money", date_paiement=jour + timedelta(days=10)
                    )
            else:
                s.add(
                    Paiement(
                        client_id=c.id,
                        vente_id=v.id,
                        montant=v.total,
                        mode=random.choice(["Espèces", "Wave", "Orange Money"]),
                        date=jour,
                    )
                )
        # Une ancienne dette du cahier, échéance dans 2 jours
        D.creer_dette(
            s,
            clients[0].id,
            15000,
            date_premiere=date.today() + timedelta(days=2),
            description="Ancienne dette (cahier)",
        )
        s.commit()
        print("Données de démonstration ajoutées.")


if __name__ == "__main__":
    main()
