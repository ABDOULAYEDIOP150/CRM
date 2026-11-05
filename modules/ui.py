"""Briques visuelles du nouveau design : icônes SVG, cartes KPI, listes, barres, logo, barre du haut.

Tout est en HTML/CSS (styles dans static/styles.css). Les textes venant de la base sont échappés.
"""

import re
from html import escape

from config import fmt_money

# Icônes (tracés Material Design, 24×24)
_SVG = {
    "alerte": "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    "attention": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z",
    "info": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z",
    "panier": "M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61"
    "-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49"
    "A1.003 1.003 0 0 0 20 4H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z",
    "hausse": "M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z",
    "portefeuille": "M21 18v1c0 1.1-.9 2-2 2H5c-1.11 0-2-.9-2-2V5c0-1.1.89-2 2-2h14c1.1 0 2 .9 2 2v1h-9c-1.11 0-2 .9-2 2"
    "v8c0 1.1.89 2 2 2h9zm-9-2h10V8H12v8zm4-2.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z",
    "carte": "M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6z"
    "m0-10H4V6h16v2z",
    "clients": "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3"
    "S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62"
    ".02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
    "cloche": "M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5"
    "s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z",
    "lieu": "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5"
    "s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z",
    "stock": "M20 2H4c-1 0-2 .9-2 2v3.01c0 .72.43 1.34 1 1.69V20c0 1.1 1.1 2 2 2h14c.9 0 2-.9 2-2V8.7c.57-.35 1-.97"
    " 1-1.69V4c0-1.1-1-2-2-2zm-5 12H9v-2h6v2zm5-7H4V4l16-.02V7z",
    "graphe": "M5 9.2h3V19H5zM10.6 5h2.8v14h-2.8zm5.6 8H19v6h-2.8z",
    "trophee": "M19 5h-2V3H7v2H5c-1.1 0-2 .9-2 2v1c0 2.55 1.92 4.63 4.39 4.94A5.01 5.01 0 0 0 11 15.9V19H7v2h10v-2h-4"
    "v-3.1a5.01 5.01 0 0 0 3.61-2.96C19.08 12.63 21 10.55 21 8V7c0-1.1-.9-2-2-2zM5 8V7h2v3.82C5.84 10.4 5 9.3 5 8zm14"
    " 0c0 1.3-.84 2.4-2 2.82V7h2v1z",
    "anneau": "M11 2v20c-5.07-.5-9-4.79-9-10s3.93-9.5 9-10zm2.03 0v8.99H22c-.47-4.74-4.24-8.52-8.97-8.99zm0 11.01V22"
    "c4.74-.47 8.5-4.25 8.97-8.99h-8.97z",
}


def icone(nom, taille=22, couleur="currentColor"):
    return (
        f"<svg width='{taille}' height='{taille}' viewBox='0 0 24 24' fill='{couleur}' aria-hidden='true'>"
        f"<path d='{_SVG[nom]}'/></svg>"
    )


# Couleurs des cartes et graphiques
BLEU, VERT, ORANGE, VIOLET, ROUGE = "#2563eb", "#16a34a", "#f59e0b", "#8b5cf6", "#ef4444"
PALETTE = [BLEU, ORANGE, VERT, VIOLET, "#0891b2", ROUGE, "#64748b", "#db2777", "#65a30d"]


def _sigle(categorie):
    """« Ciment & maçonnerie » -> CM ; « Plomberie » -> PL."""
    mots = [m for m in re.split(r"[^\wÀ-ÿ]+", categorie or "") if len(m) > 2]
    if not mots:
        return "PR"
    return (mots[0][0] + mots[1][0]) if len(mots) > 1 else mots[0][:2]


def _montant(valeur):
    """'12 480 000 FCFA' -> chiffre en gros, devise en petit."""
    texte = fmt_money(valeur)
    chiffre, _, devise = texte.rpartition(" ")
    return f"{escape(chiffre)} <small>{escape(devise)}</small>"


def carte_kpi(titre, valeur, nom_icone, couleur, variation=None, detail="", argent=True):
    """Carte colorée : icône, grand chiffre, libellé, pastille d'évolution (▲/▼ %) ou petit détail."""
    if variation is None:
        pied = f"<span class='kpi2-det'>{escape(detail)}</span>" if detail else ""
    else:
        sens = "up" if variation >= 0 else "down"
        pied = (
            f"<span class='kpi2-var {sens}'>{'▲' if variation >= 0 else '▼'} {abs(variation):.0f} %</span>"
            f"<span class='kpi2-det'>{escape(detail)}</span>"
        )
    v = _montant(valeur) if argent else escape(str(valeur))
    return (
        f"<div class='kpi2' style='--c:{couleur}'>"
        f"<div class='kpi2-ico'>{icone(nom_icone, 26, '#fff')}</div>"
        f"<div class='kpi2-corps'><div class='kpi2-v'>{v}</div><div class='kpi2-t'>{escape(titre)}</div>"
        f"<div class='kpi2-pied'>{pied}</div></div></div>"
    )


def titre_carte(texte, nom_icone, couleur=BLEU):
    return f"<div class='carte-titre'>{icone(nom_icone, 20, couleur)}<span>{escape(texte)}</span></div>"


def liste_top_produits(lignes, categories):
    """lignes : [(nom, quantité, montant)] ; categories : {nom: catégorie}."""
    html = []
    for i, (nom, qte, montant) in enumerate(lignes):
        sigle = escape(_sigle(categories.get(nom, "")).upper())
        html.append(
            f"<div class='liste-ligne'><span class='pastille sigle' style='--c:{PALETTE[i % len(PALETTE)]}'>{sigle}</span>"
            f"<span class='liste-nom'>{escape(nom)}<small>{fmt_money(montant)}</small></span>"
            f"<span class='liste-val'>{qte:g} <small>vendus</small></span></div>"
        )
    return "".join(html)


def _initiales(nom):
    mots = [m for m in nom.replace("-", " ").split() if m]
    return ((mots[0][0] + (mots[-1][0] if len(mots) > 1 else "")) if mots else "?").upper()


def liste_clients(lignes, aujourdhui):
    """lignes : [(client, montant, date)]."""
    html = []
    for i, (c, montant, quand) in enumerate(lignes):
        jours = (aujourdhui - quand.date()).days
        libelle = "Aujourd'hui" if jours == 0 else "Hier" if jours == 1 else quand.strftime("%d/%m/%Y")
        html.append(
            f"<div class='liste-ligne'><span class='avatar' style='--c:{PALETTE[i % len(PALETTE)]}'>"
            f"{escape(_initiales(c.nom))}</span>"
            f"<span class='liste-nom'>{escape(c.nom)}<small>{libelle}</small></span>"
            f"<span class='liste-val bleu'>{fmt_money(montant)}</span></div>"
        )
    return "".join(html)


def barres_progression(valeurs):
    """valeurs : {libellé: montant} -> barres en % du total."""
    total = sum(valeurs.values()) or 1
    html = []
    for i, (lib, v) in enumerate(valeurs.items()):
        pct = v / total * 100
        html.append(
            f"<div class='barre'><div class='barre-haut'><span>{escape(lib)}</span><b>{pct:.0f} %</b></div>"
            f"<div class='barre-fond'><div class='barre-plein' style='width:{pct:.1f}%;--c:{PALETTE[i % len(PALETTE)]}'>"
            f"</div></div></div>"
        )
    return "".join(html)


def legende(valeurs):
    """Légende d'anneau : pastille de couleur, libellé, pourcentage."""
    total = sum(valeurs.values()) or 1
    return (
        "<div class='legende'>"
        + "".join(
            f"<div><i style='--c:{PALETTE[i % len(PALETTE)]}'></i><span>{escape(lib)}</span><b>{v / total:.0%}</b></div>"
            for i, (lib, v) in enumerate(valeurs.items())
        )
        + "</div>"
    )


NIVEAU_ICONE = {"critique": ("alerte", ROUGE), "attention": ("attention", ORANGE), "info": ("info", BLEU)}


def liste_alertes(alertes):
    html = []
    for a in alertes:
        nom_icone, couleur = NIVEAU_ICONE.get(a.niveau, ("info", BLEU))
        montant = f"<span class='liste-val' style='color:{couleur}'>{fmt_money(a.montant)}</span>" if a.montant else ""
        html.append(
            f"<div class='liste-ligne'><span class='pastille' style='--c:{couleur}'>{icone(nom_icone, 20, couleur)}</span>"
            f"<span class='liste-nom'>{escape(a.titre)}<small>{escape(a.detail)}</small></span>{montant}</div>"
        )
    return "".join(html)


# ---------------------------------------------------------------- Menu latéral & barre du haut
LOGO_SVG = (
    "<svg width='64' height='54' viewBox='0 0 52 44' aria-hidden='true'>"
    "<path d='M4 22 L26 4 L48 22' fill='none' stroke='#f59e0b' stroke-width='4' stroke-linecap='round' "
    "stroke-linejoin='round'/>"
    "<rect x='11' y='20' width='30' height='20' rx='3' fill='#1e3a8a' stroke='#fff' stroke-width='2'/>"
    "<path d='M19 36 l8 -10' stroke='#fff' stroke-width='3' stroke-linecap='round'/>"
    "<rect x='24' y='22' width='8' height='5' rx='1' fill='#f59e0b' transform='rotate(-50 28 24.5)'/>"
    "<path d='M33 36 l-7 -9' stroke='#cbd5e1' stroke-width='2.4' stroke-linecap='round'/>"
    "<circle cx='25.5' cy='26.5' r='2.6' fill='none' stroke='#cbd5e1' stroke-width='2'/>"
    "</svg>"
)

DRAPEAU_SN = (
    "<svg width='42' height='28' viewBox='0 0 3 2' aria-label='Sénégal'>"
    "<rect width='1' height='2' fill='#00853f'/><rect x='1' width='1' height='2' fill='#fdef42'/>"
    "<rect x='2' width='1' height='2' fill='#e31b23'/>"
    "<polygon points='1.5,0.62 1.56,0.87 1.81,0.87 1.61,1.02 1.68,1.27 1.5,1.12 1.32,1.27 1.39,1.02 1.19,0.87 1.44,0.87'"
    " fill='#00853f'/></svg>"
)


def logo_menu(nom_boutique):
    return (
        f"<div class='menu-logo'>{LOGO_SVG}<div class='menu-nom'>{escape(nom_boutique)}</div>"
        f"<div class='menu-sous'>CRM PRO</div></div>"
    )


def pied_menu(nom_boutique):
    return (
        f"<div class='menu-pied'>{DRAPEAU_SN}<div class='menu-pied-nom'>{escape(nom_boutique)}</div>"
        f"<div class='menu-statut'><i></i>En ligne</div></div>"
    )


def barre_haut(titre, sous_titre, lieu, nb_alertes, boutique):
    badge = f"<span class='cloche-nb'>{nb_alertes}</span>" if nb_alertes else ""
    lieu_html = f"<span class='haut-lieu'>{icone('lieu', 18)}{escape(lieu)}</span>" if lieu else ""
    sous = f"<p>{escape(sous_titre)}</p>" if sous_titre else ""
    return (
        f"<div class='haut'><div class='haut-titre'><h1>{escape(titre)}</h1>{sous}</div>"
        f"<div class='haut-droite'>{lieu_html}"
        f"<span class='haut-cloche' title='Alertes'>{icone('cloche', 22)}{badge}</span>"
        f"<span class='haut-user'><span class='avatar' style='--c:#1e3a8a'>{escape(_initiales(boutique))}</span>"
        f"<span>{escape(boutique)}<small>Administrateur</small></span></span></div></div>"
    )


# ---------------------------------------------------------------- Tableau de bord (maquette « Gestion Pro »)
COULEUR_MODE = {
    "Espèces": VERT,
    "Wave": "#1dc4ff",
    "Orange Money": "#ff7900",
    "Free Money": "#e11d48",
    "Carte bancaire": VIOLET,
    "Virement": "#0891b2",
    "Chèque": "#64748b",
}


def titre_page(titre, sous_titre):
    return f"<div class='dash-titre'><h1>{escape(titre)}</h1><p>{escape(sous_titre)}</p></div>"


def utilisateur(nb_alertes, boutique):
    badge = f"<span class='cloche-nb'>{nb_alertes}</span>" if nb_alertes else ""
    return (
        f"<div class='dash-user'><span class='haut-cloche' title='Alertes'>{icone('cloche', 22)}{badge}</span>"
        f"<span class='avatar' style='--c:#1e3a8a'>{escape(_initiales(boutique))}</span>"
        f"<span class='dash-user-nom'>{escape(boutique)}<small>Administrateur</small></span></div>"
    )


def repartition_paiements(par_mode):
    total = sum(par_mode.values())
    if total:
        puces = "".join(
            f"<span class='rp-puce'><i style='--c:{COULEUR_MODE.get(m, '#64748b')}'></i>{escape(m)} <b>{v / total:.0%}</b></span>"
            for m, v in list(par_mode.items())[:4]
        )
    else:
        puces = "<span class='rp-puce'>Aucun encaissement</span>"
    return (
        f"<div class='rp'>{icone('carte', 18, BLEU)}<span class='rp-t'>Répartition des paiements :</span>{puces}</div>"
    )


def variation(v, libelle):
    if v is None:
        return ""
    sens = "up" if v >= 0 else "down"
    return f"<span class='var {sens}'>{'↑ +' if v >= 0 else '↓ '}{v:.0f} % {escape(libelle)}</span>"


def pastille(texte, couleur):
    return f"<span class='pas' style='--c:{couleur}'>{escape(texte)}</span>"


def grille_kpi(cartes):
    """cartes : [(titre, valeur affichée, icône, couleur, pied html, alerte)] -> une rangée de cartes égales."""
    html = []
    for titre, valeur, nom_icone, couleur, pied, alerte in cartes:
        html.append(
            f"<div class='k{' alerte' if alerte else ''}' style='--c:{couleur}'>"
            f"<div class='k-haut'><span class='k-ico'>{icone(nom_icone, 18, '#fff')}</span>"
            f"<span class='k-t'>{escape(titre)}</span></div>"
            f"<div class='k-v'>{escape(valeur)}</div><div class='k-pied'>{pied}</div></div>"
        )
    return f"<div class='k-grille'>{''.join(html)}</div>"


def tableau(colonnes, lignes, droite=(), classes_lignes=None):
    """Tableau HTML stylé. droite : indices des colonnes alignées à droite (montants)."""
    tete = "".join(f"<th class='{'d' if i in droite else ''}'>{escape(c)}</th>" for i, c in enumerate(colonnes))
    corps = []
    for n, ligne in enumerate(lignes):
        cls = (classes_lignes or {}).get(n, "")
        cellules = "".join(f"<td class='{'d' if i in droite else ''}'>{v}</td>" for i, v in enumerate(ligne))
        corps.append(f"<tr class='{cls}'>{cellules}</tr>")
    return f"<table class='tb'><thead><tr>{tete}</tr></thead><tbody>{''.join(corps)}</tbody></table>"


COULEURS_TRANCHES = [VERT, ORANGE, "#ea580c", ROUGE]


def barres_montants(valeurs, couleurs=None):
    """Barres horizontales avec montant (ex. ancienneté des dettes)."""
    maxi = max(valeurs.values(), default=0) or 1
    html = []
    for i, (lib, v) in enumerate(valeurs.items()):
        c = (couleurs or PALETTE)[i % len(couleurs or PALETTE)]
        html.append(
            f"<div class='barre'><div class='barre-haut'><span>{escape(lib)}</span><b>{fmt_money(v)}</b></div>"
            f"<div class='barre-fond'><div class='barre-plein' style='width:{v / maxi * 100:.1f}%;--c:{c}'></div></div></div>"
        )
    return "".join(html)
