"""Documents PDF remis au client.

- Facture                     : après chaque vente
- Reconnaissance de dette     : preuve signée par le client qu'il doit l'argent (montant en lettres, échéancier)
- Reçu de versement           : preuve que le client a versé de l'argent (acompte ou remboursement)
- Relevé de compte client     : toutes les dettes et tous les versements d'un client
"""

from datetime import datetime

from fpdf import FPDF

from config import fmt_date, fmt_money
from db.dettes import etat_echeances, situation_dette
from db.lettres import montant_en_lettres

ENCRE = (15, 23, 42)
GRIS = (100, 116, 139)
TRAIT = (203, 213, 225)
ACCENT = (30, 58, 138)
FOND = (241, 245, 249)


def _t(texte):
    """Les polices PDF standard ne gèrent que le latin-1."""
    texte = str(texte).replace("—", "-").replace("’", "'").replace("…", "...").replace(" ", " ")
    return texte.encode("latin-1", errors="replace").decode("latin-1")


class Document(FPDF):
    def __init__(self, params, titre, numero, date_doc):
        super().__init__(format="A4")
        self.params, self.titre, self.numero, self.date_doc = params, titre, numero, date_doc
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(True, margin=22)
        self.add_page()

    # -- mise en page commune --
    def header(self):
        p = self.params
        self.set_text_color(*ACCENT)
        self.set_font("Helvetica", "B", 16)
        self.cell(100, 8, _t(p["boutique_nom"]))
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*ENCRE)
        self.cell(0, 8, _t(self.titre), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GRIS)
        gauche = [p["boutique_adresse"], p["boutique_telephone"], p["boutique_email"]]
        droite = [f"N° {self.numero}", f"Date : {self.date_doc.strftime('%d/%m/%Y')}"]
        for i in range(max(len(gauche), len(droite))):
            self.cell(100, 4.6, _t(gauche[i] if i < len(gauche) else ""))
            self.cell(0, 4.6, _t(droite[i] if i < len(droite) else ""), align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.6)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(6)
        self.set_text_color(*ENCRE)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*TRAIT)
        self.set_line_width(0.2)
        self.line(18, self.get_y(), 192, self.get_y())
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRIS)
        p = self.params
        mentions = " · ".join(
            f"{k} : {v}" for k, v in [("NINEA", p["boutique_ninea"]), ("RCCM", p["boutique_rccm"])] if v
        )
        self.cell(120, 6, _t(mentions or p["boutique_nom"]))
        self.cell(0, 6, _t(f"Page {self.page_no()}"), align="R")

    def section(self, titre):
        self.ln(2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*GRIS)
        self.cell(0, 6, _t(titre.upper()), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*ENCRE)
        self.set_font("Helvetica", "", 10.5)

    def bloc_client(self, client, titre="Client"):
        self.section(titre)
        self.set_fill_color(*FOND)
        lignes = [client.nom if client else "-"]
        if client and client.telephone:
            lignes.append(f"Tél. : {client.telephone}")
        if client and client.adresse:
            lignes.append(client.adresse)
        y = self.get_y()
        self.rect(18, y, 174, 6 * len(lignes) + 4, "F")
        self.set_xy(22, y + 2)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, _t(lignes[0]), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        for l in lignes[1:]:
            self.set_x(22)
            self.cell(0, 6, _t(l), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def tableau(self, entetes, lignes, largeurs, aligns):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*ACCENT)
        self.set_text_color(255, 255, 255)
        for e, w, a in zip(entetes, largeurs, aligns, strict=True):
            self.cell(w, 8, _t(e), fill=True, align=a)
        self.ln()
        self.set_text_color(*ENCRE)
        self.set_font("Helvetica", "", 9.5)
        for i, ligne in enumerate(lignes):
            self.set_fill_color(*(FOND if i % 2 else (255, 255, 255)))
            for v, w, a in zip(ligne, largeurs, aligns, strict=True):
                self.cell(w, 7.5, _t(v), fill=True, align=a)
            self.ln()
        self.set_draw_color(*TRAIT)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(2)

    def total(self, libelle, montant, fort=False):
        self.set_x(110)
        self.set_font("Helvetica", "B" if fort else "", 12 if fort else 10.5)
        if fort:
            self.set_fill_color(*FOND)
        self.cell(45, 8 if fort else 6.5, _t(libelle), fill=fort)
        self.cell(37, 8 if fort else 6.5, _t(fmt_money(montant)), align="R", fill=fort, new_x="LMARGIN", new_y="NEXT")

    def paragraphe(self, texte, taille=10.5, style=""):
        self.set_font("Helvetica", style, taille)
        self.multi_cell(0, 5.8, _t(texte), new_x="LMARGIN", new_y="NEXT")

    def signatures(self, gauche, droite):
        if self.get_y() > 235:
            self.add_page()
        self.ln(8)
        y = self.get_y()
        self.set_font("Helvetica", "B", 9.5)
        for x, titre in [(18, gauche), (110, droite)]:
            self.set_xy(x, y)
            self.cell(82, 6, _t(titre))
            self.set_xy(x, y + 6)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*GRIS)
            self.cell(82, 5, _t("Lu et approuvé, date et signature"))
            self.set_text_color(*ENCRE)
            self.set_font("Helvetica", "B", 9.5)
            self.set_draw_color(*TRAIT)
            self.rect(x, y + 12, 82, 26)
        self.set_y(y + 42)

    def sortie(self):
        return bytes(self.output())


def _echeancier(pdf, dette):
    lignes = [
        (str(l["numero"]), fmt_date(l["date"]), fmt_money(l["montant"]), fmt_money(l["couvert"]), l["statut"])
        for l in etat_echeances(dette)
    ]
    if lignes:
        pdf.tableau(
            ["N°", "Date prévue", "Montant", "Déjà réglé", "Statut"],
            lignes,
            [15, 40, 40, 40, 39],
            ["C", "C", "R", "R", "C"],
        )


# --------------------------------------------------------------------------- Facture
def facture(vente, params):
    pdf = Document(params, "FACTURE", f"F-{vente.id:05d}", vente.date)
    pdf.bloc_client(vente.client, "Facturé à")
    lignes = [
        (
            vp.produit.nom if vp.produit else "Produit",
            fmt_money(vp.prix_unit),
            str(vp.quantite),
            fmt_money(vp.prix_unit * vp.quantite),
        )
        for vp in vente.produits
    ]
    pdf.tableau(["Désignation", "Prix unitaire", "Qté", "Montant"], lignes, [84, 38, 14, 38], ["L", "R", "C", "R"])
    pdf.total("Sous-total", vente.sous_total)
    if vente.remise:
        pdf.total("Remise", -vente.remise)
    pdf.total("TOTAL", vente.total, fort=True)
    pdf.ln(3)
    pdf.paragraphe(f"Arrêtée la présente facture à la somme de {montant_en_lettres(vente.total)}.", 9.5, "I")

    pdf.section("Règlement")
    d = vente.dette
    if d and d.statut != "annulee":
        pdf.paragraphe(
            f"Vente à crédit. Versé à ce jour : {fmt_money(d.total_paye)}. "
            f"Reste à payer : {fmt_money(d.reste)} (voir reconnaissance de dette D-{d.id:05d})."
        )
        _echeancier(pdf, d)
    else:
        pdf.paragraphe(f"Payée comptant le {fmt_date(vente.date)} - {vente.mode_paiement or 'Espèces'}.")
    pdf.ln(6)
    pdf.paragraphe("Merci pour votre confiance.", 9.5, "I")
    return pdf.sortie()


# --------------------------------------------------------------------------- Reconnaissance de dette
def reconnaissance_dette(dette, params):
    pdf = Document(params, "RECONNAISSANCE DE DETTE", f"D-{dette.id:05d}", dette.date_creation)
    c = dette.client
    pdf.bloc_client(c, "Le débiteur")
    pdf.section("Créancier")
    pdf.paragraphe(f"{params['boutique_nom']}, {params['boutique_adresse']} - {params['boutique_telephone']}")

    pdf.section("Déclaration")
    objet = (
        f"l'achat de marchandises (facture F-{dette.vente_id:05d})"
        if dette.vente_id
        else (dette.description or "une avance d'argent")
    )
    texte = (
        f"Je soussigné(e) {c.nom}, joignable au {c.telephone or '................'}, reconnais devoir à "
        f"{params['boutique_nom']} la somme de {fmt_money(dette.montant)} "
        f"({montant_en_lettres(dette.montant)}), au titre de {objet}, en date du {fmt_date(dette.date_creation)}."
    )
    pdf.paragraphe(texte)
    pdf.ln(2)
    if dette.acompte:
        pdf.paragraphe(
            f"J'ai versé ce jour un acompte de {fmt_money(dette.acompte)} ({montant_en_lettres(dette.acompte)}). "
            f"Il reste donc à payer {fmt_money(dette.montant - dette.acompte)} "
            f"({montant_en_lettres(dette.montant - dette.acompte)})."
        )
        pdf.ln(2)
    if dette.echeances:
        n = len(dette.echeances)
        pdf.paragraphe(
            f"Je m'engage à rembourser cette somme en {n} versement{'s' if n > 1 else ''} selon l'échéancier "
            f"ci-dessous, au plus tard le {fmt_date(dette.date_echeance_finale)}, en espèces ou par Wave / "
            f"Orange Money. Chaque versement donnera lieu à un reçu."
        )
        pdf.ln(2)
        _echeancier(pdf, dette)

    pdf.section("Situation au " + datetime.now().strftime("%d/%m/%Y"))
    pdf.total("Montant de la dette", dette.montant)
    pdf.total("Déjà versé", dette.total_paye)
    pdf.total("Reste à payer", dette.reste, fort=True)
    pdf.signatures("Le débiteur (client)", "Le créancier (boutique)")
    return pdf.sortie()


# --------------------------------------------------------------------------- Reçu
def recu(paiement, params):
    pdf = Document(params, "REÇU DE VERSEMENT", f"R-{paiement.id:05d}", paiement.date)
    pdf.bloc_client(paiement.client, "Reçu de")
    d = paiement.dette
    nature = "Acompte" if (paiement.note or "").lower() == "acompte" else "Versement"
    pdf.paragraphe(
        f"Nous reconnaissons avoir reçu de {paiement.client.nom} la somme de {fmt_money(paiement.montant)} "
        f"({montant_en_lettres(paiement.montant)}), le {paiement.date.strftime('%d/%m/%Y à %H:%M')}, "
        f"par {paiement.mode or 'espèces'}."
    )
    pdf.ln(3)
    lignes = [("Nature", nature), ("Moyen de paiement", paiement.mode or "-")]
    if d:
        lignes.insert(
            0, ("Dette concernée", f"D-{d.id:05d}" + (f" (facture F-{d.vente_id:05d})" if d.vente_id else ""))
        )
        paye_avant = sum(p.montant for p in d.paiements if (p.date, p.id) < (paiement.date, paiement.id))
        lignes += [
            ("Montant total de la dette", fmt_money(d.montant)),
            ("Déjà versé avant ce reçu", fmt_money(paye_avant)),
            ("Montant reçu", fmt_money(paiement.montant)),
            ("Reste à payer après ce versement", fmt_money(max(d.montant - paye_avant - paiement.montant, 0))),
        ]
    elif paiement.vente_id:
        lignes.insert(0, ("Facture", f"F-{paiement.vente_id:05d}"))
    if paiement.note and nature != "Acompte":
        lignes.append(("Note", paiement.note))
    pdf.tableau(["Détail", ""], lignes, [100, 74], ["L", "R"])
    pdf.signatures("Le client", "Pour la boutique (cachet et signature)")
    return pdf.sortie()


# --------------------------------------------------------------------------- Relevé client
def releve_client(client, params):
    pdf = Document(params, "RELEVÉ DE COMPTE", f"C-{client.id:05d}", datetime.now())
    pdf.bloc_client(client)
    dettes = [d for d in client.dettes if d.statut != "annulee"]
    pdf.section("Dettes")
    if dettes:
        lignes = [
            (
                f"D-{d.id:05d}",
                fmt_date(d.date_creation),
                d.description or "-",
                fmt_money(d.montant),
                fmt_money(d.total_paye),
                fmt_money(d.reste),
                situation_dette(d)["statut"],
            )
            for d in dettes
        ]
        pdf.tableau(
            ["N°", "Date", "Objet", "Montant", "Versé", "Reste", "Statut"],
            lignes,
            [20, 22, 44, 24, 22, 22, 20],
            ["L", "C", "L", "R", "R", "R", "C"],
        )
    else:
        pdf.paragraphe("Aucune dette.")
    versements = sorted((p for d in dettes for p in d.paiements), key=lambda p: p.date)
    pdf.section("Versements reçus")
    if versements:
        pdf.tableau(
            ["Reçu", "Date", "Dette", "Moyen", "Montant"],
            [
                (
                    f"R-{p.id:05d}",
                    p.date.strftime("%d/%m/%Y"),
                    f"D-{p.dette_id:05d}",
                    p.mode or "-",
                    fmt_money(p.montant),
                )
                for p in versements
            ],
            [26, 30, 30, 50, 38],
            ["L", "C", "C", "L", "R"],
        )
    else:
        pdf.paragraphe("Aucun versement.")
    pdf.ln(2)
    total_reste = sum(d.reste for d in dettes if d.statut == "en_cours")
    pdf.total("Total restant dû", total_reste, fort=True)
    pdf.paragraphe(f"Soit {montant_en_lettres(total_reste)}.", 9.5, "I")
    return pdf.sortie()
