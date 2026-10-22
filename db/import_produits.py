"""Import de produits depuis un fichier Excel ou CSV (sans saisie manuelle).

- Les colonnes sont reconnues même si elles sont nommées différemment (« Désignation », « Qté », « PV »…).
- Un produit déjà en base (même référence, sinon même nom) est mis à jour ; sinon il est créé.
- Rien n'est écrit tant qu'on n'a pas appelé `appliquer` : on peut d'abord montrer un aperçu.
"""

import io
import re
import unicodedata

import pandas as pd

from .models import Produit
from .stock import fixer_stock, mouvement

COLONNES = {
    "nom": ["nom", "produit", "designation", "article", "libelle", "nomduproduit", "description"],
    "categorie": ["categorie", "famille", "rayon", "type", "categorieproduit"],
    "unite": ["unite", "unitedevente", "conditionnement", "u", "unitemesure", "unitedemesure"],
    "prix": ["prixdevente", "prix", "pv", "prixvente", "prixunitaire", "tarif", "prixdeventefcfa"],
    "prix_achat": ["prixdachat", "prixachat", "pa", "cout", "coutdachat", "prixdachatfcfa"],
    "stock": ["stock", "quantite", "qte", "qty", "quantiteenstock", "stockactuel", "quantitedisponible"],
    "seuil_alerte": ["seuildalerte", "seuil", "alerte", "stockmin", "stockminimum", "seuilalerte"],
    "reference": ["reference", "ref", "code", "codebarre", "codebarres", "sku", "codearticle"],
}
ENTETES_MODELE = {
    "nom": "Nom", "categorie": "Catégorie", "unite": "Unité", "prix": "Prix de vente",
    "prix_achat": "Prix d'achat", "stock": "Stock", "seuil_alerte": "Seuil d'alerte", "reference": "Référence",
}  # fmt: skip
NOUVEAU, MAJ, INCHANGE, ERREUR = "Nouveau", "Mise à jour", "Inchangé", "Erreur"


def _cle(texte):
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def reconnaitre_colonnes(colonnes):
    """{'nom': 'Désignation', 'stock': 'Qté', …} à partir des entêtes du fichier."""
    trouvees = {}
    for col in colonnes:
        k = _cle(col)
        for champ, synonymes in COLONNES.items():
            if champ not in trouvees and k in synonymes:
                trouvees[champ] = col
    return trouvees


def nombre(valeur):
    """'4 600 FCFA' -> 4600 ; '' -> None ; 'abc' -> ValueError."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return None
    if isinstance(valeur, int | float):
        return round(float(valeur))
    texte = re.sub(r"(?i)\s|fcfa|cfa|xof|f$", "", str(valeur).replace(" ", "").replace("\xa0", ""))
    if texte == "":
        return None
    texte = texte.replace(".", "").replace(",", "")
    if not re.fullmatch(r"-?\d+", texte):
        raise ValueError(f"« {valeur} » n'est pas un nombre")
    return int(texte)


def lire_fichier(nom_fichier, contenu: bytes):
    if nom_fichier.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(contenu), dtype=object)
    texte = contenu.decode("utf-8-sig", errors="replace")
    sep = ";" if texte.count(";") > texte.count(",") else ","
    return pd.read_csv(io.StringIO(texte), sep=sep, dtype=object)


def analyser(session, df):
    """Retourne (lignes, colonnes reconnues). Chaque ligne : n°, nom, action, détail, valeurs, produit_id."""
    cols = reconnaitre_colonnes(df.columns)
    if "nom" not in cols:
        raise ValueError("Colonne du nom de produit introuvable (attendu : « Nom », « Produit » ou « Désignation »).")
    existants = session.query(Produit).all()
    par_nom = {p.nom.strip().lower(): p for p in existants}
    par_ref = {p.reference.strip().lower(): p for p in existants if p.reference}
    vus, lignes = set(), []
    for i, row in df.iterrows():
        n = i + 2  # numéro de ligne Excel (ligne 1 = entêtes)
        nom = str(row[cols["nom"]]).strip() if pd.notna(row[cols["nom"]]) else ""
        if not nom:
            continue  # ligne vide
        valeurs, erreurs = {"nom": nom}, []
        for champ in ("categorie", "unite", "reference"):
            if champ in cols and pd.notna(row[cols[champ]]) and str(row[cols[champ]]).strip():
                valeurs[champ] = str(row[cols[champ]]).strip()
        if "unite" in valeurs:
            valeurs["unite"] = valeurs["unite"].lower()
        for champ in ("prix", "prix_achat", "stock", "seuil_alerte"):
            if champ in cols:
                try:
                    v = nombre(row[cols[champ]])
                except ValueError as e:
                    erreurs.append(f"{ENTETES_MODELE[champ]} : {e}")
                    continue
                if v is not None:
                    if v < 0:
                        erreurs.append(f"{ENTETES_MODELE[champ]} négatif")
                    valeurs[champ] = v
        ref = valeurs.get("reference", "").lower()
        produit = par_ref.get(ref) if ref else None
        produit = produit or par_nom.get(nom.lower())
        cle = ref or nom.lower()
        if cle in vus:
            erreurs.append("produit présent deux fois dans le fichier")
        vus.add(cle)
        if produit is None and "prix" not in valeurs:
            erreurs.append("prix de vente manquant pour un nouveau produit")

        if erreurs:
            action, detail = ERREUR, " ; ".join(erreurs)
        elif produit is None:
            action, detail = NOUVEAU, ""
        else:
            changes = [ENTETES_MODELE[k] for k, v in valeurs.items()
                       if k != "nom" and getattr(produit, k) != v and not (k == "stock")]  # fmt: skip
            if "stock" in valeurs:
                changes.append("Stock")
            action = MAJ if changes or produit.nom != nom else INCHANGE
            detail = ", ".join(changes)
        lignes.append({"ligne": n, "nom": nom, "action": action, "detail": detail, "valeurs": valeurs,
                       "produit_id": produit.id if produit else None})  # fmt: skip
    return lignes, cols


def appliquer(session, lignes, mode_stock="remplacer"):
    """Écrit en base les lignes valides. mode_stock : 'remplacer' (inventaire) ou 'ajouter' (arrivage)."""
    compte = {NOUVEAU: 0, MAJ: 0}
    for l in lignes:
        if l["action"] not in (NOUVEAU, MAJ):
            continue
        v = dict(l["valeurs"])
        stock = v.pop("stock", None)
        if l["action"] == NOUVEAU:
            p = Produit(**{"stock": 0, "categorie": "Divers", "unite": "pièce", "prix_achat": 0, **v})
            session.add(p)
            session.flush()
            if stock:
                mouvement(session, p, stock, "Import", "Import Excel (nouveau produit)")
        else:
            p = session.get(Produit, l["produit_id"])
            for k, val in v.items():
                setattr(p, k, val)
            if stock is not None:
                if mode_stock == "ajouter":
                    mouvement(session, p, stock, "Import", "Import Excel (arrivage)")
                else:
                    fixer_stock(session, p, stock, "Import", "Import Excel (inventaire)")
        compte[l["action"]] += 1
    session.flush()
    return compte


def modele_excel(produits=None):
    """Fichier Excel prêt à remplir : le catalogue actuel (pour le modifier) ou des exemples."""
    if produits:
        lignes = [[p.nom, p.categorie, p.unite, p.prix, p.prix_achat, p.stock, p.seuil_alerte, p.reference]
                  for p in produits]  # fmt: skip
    else:
        lignes = [
            ["Ciment CPJ 45 - 50 kg", "Ciment & maçonnerie", "sac", 4600, 4150, 100, 20, "CIM50"],
            ["Fer à béton 10 mm", "Fer & métaux", "barre", 3500, 3000, 60, 15, "FER10"],
            ["Café Touba 250 g", "Alimentation", "paquet", 1000, 800, 40, 10, ""],
        ]
    df = pd.DataFrame(lignes, columns=list(ENTETES_MODELE.values()))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Produits", index=False)
        ws = w.sheets["Produits"]
        for col, largeur in zip("ABCDEFGH", [32, 24, 12, 15, 15, 10, 15, 14], strict=True):
            ws.column_dimensions[col].width = largeur
    return buf.getvalue()
