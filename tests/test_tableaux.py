"""Mise en forme des tableaux : couleurs selon le statut, le stock et les montants."""

import pandas as pd

from modules.tableaux import ORANGE, ROUGE, VERT, style_statut, styliser


def test_couleurs_des_statuts():
    assert style_statut("En retard (31 j)") == ROUGE
    assert style_statut("Rupture") == ROUGE
    assert style_statut("Faible") == ORANGE
    assert style_statut("À jour") == VERT and style_statut("Payée") == VERT and style_statut("OK") == VERT
    assert style_statut("") == ""


def test_styliser_ne_change_pas_les_valeurs():
    df = pd.DataFrame({"Produit": ["Ciment", "Sable", "Fer"], "Stock": [0, 3, 50], "Seuil d'alerte": [5, 5, 5],
                       "Prix de vente": [4300, 15000, 3700], "Reste": [0, 1200, 0], "État": ["Rupture", "Faible", "OK"]})  # fmt: skip
    sty = styliser(df)
    assert sty.data.equals(df)  # mêmes données : tri et formats Streamlit intacts
    css = sty._compute().ctx
    st_col, etat = list(df.columns).index("Stock"), list(df.columns).index("État")
    assert ("color", "#b91c1c") in css[(0, st_col)]  # stock à 0 en rouge
    assert ("color", "#b45309") in css[(1, st_col)]  # sous le seuil en orange
    assert ("color", "#15803d") in css[(2, etat)]  # OK en vert
    assert styliser(pd.DataFrame()).empty  # tableau vide accepté
