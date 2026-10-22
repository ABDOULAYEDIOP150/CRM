"""Guide rapide : de quoi former un vendeur en 10 minutes."""

import streamlit as st

import config

GUIDES = [
    (
        "🛒 Faire une vente payée comptant",
        [
            "Menu **Nouvelle vente**.",
            "Tapez les premières lettres du produit dans la barre de recherche (ex. « ci » → Ciment) et appuyez sur Entrée. "
            "Vous pouvez aussi cliquer sur **➕ Ajouter** sous un produit.",
            "Changez la quantité dans le panier si besoin (🗑️ pour retirer un produit).",
            "Laissez **💵 Payé comptant**, choisissez Espèces / Wave / Orange Money. Pour les espèces, tapez le montant "
            "reçu : la monnaie à rendre s'affiche.",
            "Cliquez sur **✅ Valider la vente**, puis téléchargez la **facture** si le client la demande.",
        ],
    ),
    (
        "📝 Vendre à crédit (dette)",
        [
            "Comme une vente normale, mais choisissez **le client** (ou créez-le avec ➕ : nom + téléphone).",
            "Cliquez sur **📝 À crédit (dette)**.",
            "Indiquez l'**avance** que le client donne aujourd'hui (0 s'il ne donne rien), en **combien de fois** il "
            "paiera le reste, et la **date du 1er paiement**.",
            "Validez, puis imprimez la **reconnaissance de dette** et faites-la **signer par le client**. "
            "S'il a donné une avance, remettez-lui le **reçu**.",
        ],
    ),
    (
        "💰 Encaisser un remboursement",
        [
            "Menu **Dettes clients** (ou bouton *Encaisser une dette* sur le tableau de bord).",
            "Tapez le nom du client dans la recherche puis **cliquez sur la ligne** de sa dette.",
            "Cliquez sur **💰 Encaisser un versement**, tapez le montant reçu, validez.",
            "Téléchargez le **reçu** et remettez-le au client.",
        ],
    ),
    (
        "🔔 Comprendre les alertes",
        [
            "🔴 **Urgent** : un client est en retard de paiement, ou un produit est en rupture.",
            "🟠 **À surveiller** : un client doit payer aujourd'hui ou dans les 2 jours, un stock est faible, "
            "un client dépasse son plafond de crédit.",
            "ℹ️ **Pour information** : produits qui ne se vendent pas, prix d'achat manquants.",
            "Chaque alerte a un bouton pour agir directement (encaisser, relancer sur WhatsApp, réapprovisionner).",
        ],
    ),
    (
        "📦 Gérer le stock",
        [
            "Le **Catalogue produits** est la liste de vos produits : nom, **code** (ex. SAB-001), catégorie, unité. "
            "Pas de prix ni de quantité ici.",
            "À chaque achat chez un fournisseur : **Entrée de stock** → tapez le code ou le nom du produit, la "
            "**quantité achetée**, le **prix d'achat** (par unité ou total payé) et le **prix de vente**. "
            "La marge s'affiche avant de valider.",
            "Chaque arrivage garde son prix d'achat : les plus anciens sont vendus en premier, le bénéfice reste exact.",
            "**État du stock** : quantités, valeur, marge, détail des arrivages ; changez un prix de vente sans racheter.",
            "**Inventaire** : tapez ce que vous avez compté, les écarts sont corrigés et notés dans le journal.",
            "Beaucoup de produits ? **Catalogue → Importer depuis Excel**.",
        ],
    ),
    (
        "📄 Retrouver une facture ou un reçu",
        [
            "Menu **Ventes & documents** : choisissez la période, cliquez sur la vente.",
            "Les boutons permettent de retélécharger la facture, la reconnaissance de dette et les reçus.",
            "Le **relevé de compte** d'un client se trouve dans sa fiche (menu **Clients**).",
        ],
    ),
]


def show_aide():
    config.entete("Guide rapide", "Tout ce qu'il faut savoir pour utiliser l'application, en 6 fiches.")
    st.info("💡 Astuce : le **tableau de bord** est la page d'accueil. Commencez chaque journée par les **alertes**.")
    for i, (titre, etapes) in enumerate(GUIDES):
        with st.expander(titre, expanded=i == 0):
            for n, e in enumerate(etapes, 1):
                st.markdown(f"**{n}.** {e}")
