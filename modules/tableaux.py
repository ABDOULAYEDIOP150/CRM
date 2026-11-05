"""Mise en forme commune de tous les tableaux (st.dataframe et st.data_editor).

Les colonnes sont reconnues par leur nom : on passe simplement `styliser(df)` au lieu de `df`.
- lignes alternées (zébrées) ;
- colonnes de statut (État, Statut, Situation, Action, Type) : pastille de couleur selon la valeur ;
- montants (Prix, Total, Montant, Valeur…) en bleu foncé ; ce qui reste dû en orange ;
- stock à zéro en rouge, stock sous le seuil en orange ;
- quantités de mouvement : entrée en vert, sortie en rouge.
Les valeurs ne sont pas modifiées : tri, filtres et formats des colonnes restent ceux de Streamlit.
"""

import pandas as pd

ZEBRE = "background-color: #f7f9fc"
ROUGE = "color: #b91c1c; background-color: #fee2e2"
ORANGE = "color: #b45309; background-color: #fef3c7"
VERT = "color: #15803d; background-color: #dcfce7"
BLEU = "color: #1d4ed8; background-color: #e0eafc"
VIOLET = "color: #6d28d9; background-color: #ede9fe"
GRIS = "color: #475569; background-color: #eef2f7"

COLONNES_STATUT = {"État", "Statut", "Situation", "Action", "Type"}
MOTS_MONTANT = ("prix", "total", "montant", "valeur", "payé", "versé", "vente (", "achat (", "achats", "ca", "fcfa")
MOTS_DU = ("reste", "doit", "solde", "dû")

# Premier mot-clé trouvé dans la valeur (en minuscules) -> style
STATUTS = [
    (("retard", "rupture", "annul", "erreur", "perte", "insuffisant"), ROUGE),
    (("faible", "en cours", "proche", "attente", "correction"), ORANGE),
    (("ok", "à jour", "payé", "soldé", "nouveau", "réception", "remboursé"), VERT),
    (("mise à jour", "vente", "crédit"), BLEU),
    (("inventaire", "import"), VIOLET),
    (("jamais", "inchangé", "création"), GRIS),
]


def style_statut(valeur):
    texte = str(valeur).strip().lower()
    if not texte or texte in ("nan", "none"):
        return ""
    for mots, style in STATUTS:
        if any(texte.startswith(m) or f" {m}" in f" {texte}" for m in mots):
            return style
    return GRIS


def _nombre(v):
    try:
        return float(str(v).split()[0].replace(" ", "").replace(" ", "").replace(",", "."))
    except (ValueError, IndexError):
        return None


def styliser(df: pd.DataFrame):
    """Renvoie un Styler pandas prêt pour st.dataframe / st.data_editor."""
    if df is None or df.empty:
        return df
    sty = df.style
    sty = sty.apply(lambda ligne: [ZEBRE if ligne.name % 2 else ""] * len(ligne), axis=1) if isinstance(
        df.index, pd.RangeIndex
    ) else sty  # fmt: skip

    colonnes = list(df.columns)
    bas = {c: str(c).lower() for c in colonnes}

    statut = [c for c in colonnes if c in COLONNES_STATUT]
    if statut:
        sty = sty.map(style_statut, subset=statut)

    dus = [c for c in colonnes if any(m in bas[c] for m in MOTS_DU) and "stock" not in bas[c]]
    montants = [
        c for c in colonnes
        if c not in dus and any(m in bas[c] for m in MOTS_MONTANT) and pd.api.types.is_numeric_dtype(df[c])
    ]  # fmt: skip
    if montants:
        sty = sty.map(lambda v: "color: #1e3a8a", subset=montants)
    if dus:
        sty = sty.map(lambda v: "color: #c2410c" if (_nombre(v) or 0) > 0 else "color: #15803d", subset=dus)

    stock = next((c for c in colonnes if bas[c].startswith("stock") and "après" not in bas[c]), None)
    seuil = next((c for c in colonnes if bas[c].startswith("seuil")), None)
    if stock is not None:

        def couleur_stock(ligne):
            n = _nombre(ligne[stock])
            s = _nombre(ligne[seuil]) if seuil is not None else None
            if n is None:
                return [""] * len(ligne)
            jamais = any(str(ligne[c]).lower().startswith("jamais") for c in statut)
            style = GRIS if jamais and n <= 0 else ROUGE if n <= 0 else (ORANGE if s is not None and n <= s else "")
            return [style if c == stock else "" for c in ligne.index]

        sty = sty.apply(couleur_stock, axis=1)

    for c in ("Quantité", "Qté"):
        if c in colonnes and pd.api.types.is_numeric_dtype(df[c]) and "Type" in colonnes:
            sty = sty.map(lambda v: "color: #15803d" if v > 0 else ("color: #b91c1c" if v < 0 else ""), subset=[c])
    return sty
