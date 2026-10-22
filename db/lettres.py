"""Conversion d'un montant en toutes lettres (français), pour les documents officiels."""

_UNITES = [
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf",
]  # fmt: skip
_DIZAINES = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _moins_de_100(n, final=True):
    if n < 20:
        return _UNITES[n]
    d, u = divmod(n, 10)
    if d in (7, 9):  # 70-79 = soixante-dix…, 90-99 = quatre-vingt-dix…
        base = "soixante" if d == 7 else "quatre-vingt"
        reste = 10 + u
        liaison = " et " if (d == 7 and u == 1) else "-"
        return base + liaison + _UNITES[reste]
    if d == 8:
        return ("quatre-vingts" if final else "quatre-vingt") if u == 0 else "quatre-vingt-" + _UNITES[u]
    if u == 0:
        return _DIZAINES[d]
    if u == 1:
        return _DIZAINES[d] + " et un"
    return _DIZAINES[d] + "-" + _UNITES[u]


def _moins_de_1000(n, final=True):
    c, r = divmod(n, 100)
    if c == 0:
        return _moins_de_100(r, final)
    centaine = "cent" if c == 1 else _UNITES[c] + " cent"
    if r == 0:
        return centaine + ("s" if c > 1 and final else "")
    return centaine + " " + _moins_de_100(r, final)


def en_lettres(n):
    """1250 -> 'mille deux cent cinquante'."""
    n = int(round(n))
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + en_lettres(-n)
    morceaux = []
    for valeur, sing, plur in [(10**9, "milliard", "milliards"), (10**6, "million", "millions")]:
        q, n = divmod(n, valeur)
        if q:
            morceaux.append(f"{_moins_de_1000(q)} {sing if q == 1 else plur}")
    q, n = divmod(n, 1000)
    if q:
        morceaux.append("mille" if q == 1 else _moins_de_1000(q, final=False) + " mille")
    if n:
        morceaux.append(_moins_de_1000(n))
    return " ".join(morceaux)


def montant_en_lettres(n, devise="francs CFA"):
    return f"{en_lettres(n)} {devise}"
