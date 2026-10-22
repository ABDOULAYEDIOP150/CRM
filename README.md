# 🚀 CRM PRO - Application de Gestion Commerciale & Données Clients

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-green)
![Streamlit](https://img.shields.io/badge/streamlit-1.28%2B-red)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 🎯 Aperçu

**CRM Pro** est une application de gestion commerciale et de pilotage des données clients, développée dans une logique proche des outils CRM professionnels (type Salesforce, Coheris).

L’objectif est de centraliser, structurer et exploiter les données clients afin d’améliorer le suivi commercial, la prise de décision et la performance globale.

👉 Ce projet s’inscrit dans une démarche de :

* structuration des données CRM
* pilotage d’activité commerciale
* support à la décision via indicateurs

---

## 📸 Capture d’écran

![Interface CRM Pro](logo.png)

*Exemple : tableau de bord et interface de gestion (clients, produits, ventes)*

👉 L’application comporte plusieurs modules :

* Dashboard (indicateurs clés)
* Gestion des clients
* Gestion des produits
* Gestion des ventes
* Facturation

---

## 💡 Problématique métier

Dans de nombreuses organisations, les données clients sont :

* dispersées (Excel, outils multiples)
* peu structurées
* difficilement exploitables

👉 CRM Pro répond à ces enjeux en proposant :

* une base de données centralisée
* une vision 360° du client
* des indicateurs de performance en temps réel

---

## 🧠 Fonctionnalités principales

### 💳 Gestion des dettes (nouveau en v3)

Pensé pour les boutiques au Sénégal, où la vente « à crédit » est courante :

* **Vente à crédit** directement depuis la caisse, avec **acompte** versé le jour même
* **Échéancier** : nombre de versements + fréquence (hebdomadaire, toutes les 2 semaines, mensuelle)
* **Remboursements partiels** (Espèces, Wave, Orange Money, Free Money…) avec **reçu PDF**
* Statut automatique de chaque dette : 🟢 À jour · 🔴 En retard (avec nombre de jours) · ✅ Soldée
* **Rééchelonnement** quand un client demande plus de temps, annulation en cas d'erreur
* **Plafond de crédit** par client + alerte si le client a déjà une dette en retard
* **Dettes manuelles** pour reprendre les anciennes dettes du cahier ou un prêt d'argent
* **Relance en un clic** par WhatsApp ou SMS avec un message pré-rempli (modifiable)

### 📊 Tableau de bord & alertes

* KPI par période : CA, **encaissé**, marge estimée, **dettes à recevoir**, **montant en retard**
* 🔔 Alertes : dettes en retard, échéances dans les X prochains jours, stock faible
* Graphiques : ventes vs encaissements, top débiteurs, top produits, moyens de paiement

### 👥 Clients · 📦 Produits · 🛒 Ventes · 📄 Factures

* Création **et modification** des clients (adresse, plafond, notes) et des produits (prix d'achat, réapprovisionnement)
* Panier modifiable, **remise**, vérification du stock au moment de valider
* Factures PDF avec situation de paiement (payé / reste à payer / échéancier)
* Historique filtrable par période, exports CSV
* ⚙️ Paramètres de la boutique (nom, téléphone, NINEA, RCCM…) repris sur les factures et reçus
* Montants en **FCFA**

![Tableau de bord](docs/dashboard.png)
![Dettes](docs/dettes.png)

---

## 🏗️ Architecture & Structure du projet

```bash
CRM/
│── app_crm.py              # Application Streamlit (menu + routage)
│── config.py               # Paramètres, couleurs, formatage FCFA
│── demo_data.py            # Données de démonstration
│── db/
│   ├── models.py           # Modèles SQLAlchemy + migration automatique de l'ancienne base
│   ├── dettes.py           # Logique métier des dettes (échéancier, retards, relances)
│   └── utils.py            # Statistiques et paramètres
│── modules/                # Pages : dashboard, clients, produits, ventes, dettes, factures, historique, parametres
│   └── pdf_utils.py        # Factures et reçus PDF
│── tests/                  # Tests pytest (logique des dettes + chaque page)
│── static/styles.css
```

---

## 🧩 Modélisation des données

Le projet repose sur une structuration des données proche des CRM :

* **Clients** : informations personnelles, historique
* **Produits** : catalogue et stock
* **Ventes** : transactions liées aux clients
* **Factures** : documents générés
* **Dettes** → **Échéances** (plan de remboursement) et **Paiements** (tous les encaissements)

👉 Cette modélisation permet :

* une meilleure exploitation des données
* une analyse du parcours client
* une base pour marketing relationnel

---

## ⚙️ Technologies utilisées

* **Python** (logique applicative)
* **Streamlit** (interface utilisateur)
* **Pandas** (traitement des données)
* **SQLite + SQLAlchemy** (stockage des données)
* **fpdf2** (factures et reçus PDF)
* **Plotly** (graphiques)
* **pytest** (tests)

---

## 🔄 Logique projet (approche applicative)

Ce projet a été conçu dans une logique de :

* gestion d’un système applicatif CRM
* évolution progressive des fonctionnalités
* adaptation aux besoins métier
* amélioration continue

👉 Il simule le rôle de :
**Responsable applicatif / Data orienté CRM**

---

## 🚀 Installation

### Prérequis

* Python 3.8+
* pip

### Étapes

```bash
git clone https://github.com/ABDOULAYEDIOP150/CRM.git
cd CRM

python -m venv venv

# Activation
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt

python demo_data.py        # optionnel : données de démonstration
streamlit run app_crm.py
```

Une base créée avec une ancienne version est mise à jour automatiquement au lancement (aucune donnée perdue).

Lancer les tests : `python -m pytest -q`

---

## ▶️ Utilisation

1. Accéder au tableau de bord
2. Ajouter des clients / produits
3. Enregistrer des ventes
4. Générer des factures
5. Analyser les performances

---

## 📈 Perspectives d’amélioration

* Comptes utilisateurs (gérant / vendeur) et journal des actions
* Envoi automatique des relances WhatsApp (API WhatsApp Business)
* Paiement Wave / Orange Money par lien ou QR code
* Mode hors-ligne / application mobile, multi-boutiques
* Intégration d’une base SQL (PostgreSQL / MySQL)
* Ajout d’API pour interconnexion (approche SI)
* Module de marketing automation (emailing)
* Gestion des utilisateurs / rôles
* Intégration RGPD (gestion consentement)

---

## 🤝 Contribution

Les contributions sont les bienvenues :

* amélioration des fonctionnalités
* optimisation technique
* ajout de modules CRM

---

## 📄 Licence

Projet sous licence MIT

---

## 📬 Contact

**Abdoulaye Diop**
📧 [diop.abdoulaye.stats@gmail.com](mailto:diop.abdoulaye.stats@gmail.com)
🔗 LinkedIn : https://www.linkedin.com/in/abdoulaye-diop-71467b361/

---
