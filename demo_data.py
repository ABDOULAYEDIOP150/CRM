"""
Remplit la base avec des données de démonstration (boutique à Dakar).
Usage :  python demo_data.py        (n'ajoute rien si des clients existent déjà)
"""
import random
from datetime import date, datetime, timedelta

from db.models import get_session, Client, Produit, Vente, VenteProduit, HistoriqueVente, Paiement
from db import dettes as D

CLIENTS = [("Awa Ndiaye", "77 412 33 10", "Parcelles Assainies"), ("Moussa Fall", "78 220 45 91", "Médina"),
           ("Fatou Diop", "76 900 12 34", "Grand Yoff"), ("Ibrahima Sarr", "70 555 66 77", "Pikine"),
           ("Aminata Ba", "77 300 88 21", "Liberté 6"), ("Cheikh Mbaye", "78 111 22 33", "Guédiawaye")]
PRODUITS = [("Riz parfumé 25 kg", 17500, 15500, 30), ("Huile 5 L", 6500, 5600, 25), ("Sucre 1 kg", 700, 600, 80),
            ("Lait en poudre 400 g", 2500, 2100, 2), ("Thé vert (paquet)", 1000, 800, 40),
            ("Savon (carton)", 9000, 7800, 10), ("Téléphone Itel", 25000, 21000, 5)]


def main():
    random.seed(7)
    with get_session() as s:
        if s.query(Client).count():
            print("La base contient déjà des clients : rien à faire.")
            return
        clients = [Client(nom=n, telephone=t, adresse=a, plafond_credit=random.choice([0, 50000, 100000]),
                          date_creation=datetime.now() - timedelta(days=90)) for n, t, a in CLIENTS]
        produits = [Produit(nom=n, prix=p, prix_achat=pa, stock=st) for n, p, pa, st in PRODUITS]
        s.add_all(clients + produits)
        s.flush()
        for i in range(25):
            jour = datetime.now() - timedelta(days=random.randint(0, 60), hours=random.randint(0, 8))
            c = random.choice(clients)
            v = Vente(client_id=c.id, date=jour, mode_livraison="Retrait en magasin", mode_paiement="Espèces")
            s.add(v)
            s.flush()
            for p in random.sample(produits[:-1], k=random.randint(1, 3)):
                q = random.randint(1, 3)
                s.add(VenteProduit(vente_id=v.id, produit_id=p.id, quantite=q, prix_unit=p.prix))
                s.add(HistoriqueVente(vente_id=v.id, client_nom=c.nom, client_telephone=c.telephone,
                                      produit_nom=p.nom, quantite=q, prix_unit=p.prix, date=jour))
            s.flush()
            s.refresh(v)
            if i % 4 == 0:  # vente à crédit
                v.mode_paiement = "Crédit"
                d = D.creer_dette(s, c.id, v.total, nb_versements=random.choice([1, 2, 3]),
                                  date_premiere=(jour + timedelta(days=random.choice([7, 15, 30]))).date(),
                                  frequence="Toutes les 2 semaines", acompte=round(v.total * 0.2, -2),
                                  mode_acompte="Wave", vente_id=v.id, description=f"Vente F-{v.id:05d}",
                                  date_creation=jour)
                if random.random() < 0.5 and d.reste > 0:
                    D.enregistrer_paiement(s, d, round(d.reste / 2), "Orange Money",
                                           date_paiement=jour + timedelta(days=10))
            else:
                s.add(Paiement(client_id=c.id, vente_id=v.id, montant=v.total,
                               mode=random.choice(["Espèces", "Wave", "Orange Money"]), date=jour))
        # Une ancienne dette du cahier, échéance dans 2 jours
        D.creer_dette(s, clients[0].id, 15000, date_premiere=date.today() + timedelta(days=2),
                      description="Ancienne dette (cahier)")
        s.commit()
        print("Données de démonstration ajoutées.")


if __name__ == "__main__":
    main()
