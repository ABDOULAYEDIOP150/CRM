"""Génération des PDF : factures (avec situation de paiement) et reçus de paiement."""

from datetime import datetime

from fpdf import FPDF

from config import fmt_date, fmt_money
from db.dettes import etat_echeances

BLEU = (30, 58, 138)
BLEU2 = (37, 99, 235)
BLEU_CLAIR = (219, 234, 254)


def _t(texte):
    """Les polices PDF standard ne gèrent que le latin-1 : on remplace le reste."""
    texte = str(texte).replace("—", "-").replace("’", "'").replace("…", "...")
    return texte.encode("latin-1", errors="replace").decode("latin-1")


class PDF(FPDF):
    def __init__(self, params):
        super().__init__()
        self.params = params
        self.set_auto_page_break(True, margin=20)

    def header(self):
        self.set_fill_color(*BLEU)
        self.rect(0, 0, 210, 32, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 22)
        self.set_y(8)
        self.cell(0, 12, _t(self.params["boutique_nom"].upper()), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        infos = " | ".join(
            x
            for x in [self.params["boutique_adresse"], self.params["boutique_telephone"], self.params["boutique_email"]]
            if x
        )
        self.cell(0, 6, _t(infos), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_y(40)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        mentions = [("NINEA", self.params["boutique_ninea"]), ("RCCM", self.params["boutique_rccm"])]
        legal = " - ".join(f"{nom} : {val}" for nom, val in mentions if val)
        self.cell(0, 5, _t(legal or "Merci pour votre confiance !"), align="C")

    def titre_bandeau(self, texte):
        self.set_fill_color(*BLEU2)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, _t(texte), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 11)
        self.ln(2)

    def ligne(self, gauche, droite, gras=False):
        self.set_font("Helvetica", "B" if gras else "", 11)
        self.cell(130, 7, _t(gauche))
        self.cell(60, 7, _t(droite), align="R", new_x="LMARGIN", new_y="NEXT")


def generer_facture(vente, params):
    pdf = PDF(params)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, "FACTURE", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(95, 7, _t(f"Facture N° F-{vente.id:05d}"))
    pdf.cell(95, 7, _t(f"Date : {vente.date.strftime('%d/%m/%Y %H:%M')}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.titre_bandeau("FACTURÉ À")
    c = vente.client
    pdf.cell(0, 6, _t(f"Client : {c.nom if c else 'Client supprimé'}"), new_x="LMARGIN", new_y="NEXT")
    if c:
        pdf.cell(0, 6, _t(f"Téléphone : {c.telephone or ''}"), new_x="LMARGIN", new_y="NEXT")
        if c.adresse:
            pdf.cell(0, 6, _t(f"Adresse : {c.adresse}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _t(f"Livraison : {vente.mode_livraison or '-'}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Tableau des produits
    pdf.set_fill_color(*BLEU2)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    for txt, w in [("Produit", 80), ("Prix unit.", 40), ("Qté", 20), ("Total", 50)]:
        pdf.cell(w, 9, _t(txt), border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    for vp in vente.produits:
        nom = vp.produit.nom if vp.produit else "Produit inconnu"
        nom = nom if len(nom) <= 38 else nom[:35] + "..."
        pdf.cell(80, 8, _t(nom), border=1)
        pdf.cell(40, 8, _t(fmt_money(vp.prix_unit)), border=1, align="R")
        pdf.cell(20, 8, str(vp.quantite), border=1, align="C")
        pdf.cell(50, 8, _t(fmt_money(vp.prix_unit * vp.quantite)), border=1, align="R")
        pdf.ln()
    pdf.ln(3)

    pdf.ligne("Sous-total", fmt_money(vente.sous_total))
    if vente.remise:
        pdf.ligne("Remise", "- " + fmt_money(vente.remise))
    pdf.set_fill_color(*BLEU_CLAIR)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(130, 10, _t("TOTAL À PAYER"), fill=True)
    pdf.cell(60, 10, _t(fmt_money(vente.total)), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Situation de paiement
    pdf.titre_bandeau("RÈGLEMENT")
    dette = vente.dette
    if dette and dette.statut != "annulee":
        pdf.ligne("Déjà payé", fmt_money(dette.total_paye))
        pdf.ligne("Reste à payer", fmt_money(dette.reste), gras=True)
        if dette.reste > 0 and dette.echeances:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, _t("Échéancier de remboursement :"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for l in etat_echeances(dette):
                pdf.cell(
                    0,
                    6,
                    _t(
                        f"  {l['numero']}. {fmt_date(l['date'])} : {fmt_money(l['montant'])}"
                        + (f" - reste {fmt_money(l['reste'])}" if 0 < l["couvert"] < l["montant"] else "")
                        + f"  ({l['statut']})"
                    ),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
    else:
        pdf.ligne(f"Payé comptant ({vente.mode_paiement or 'Espèces'})", fmt_money(vente.total))
        pdf.ligne("Reste à payer", fmt_money(0), gras=True)
    return bytes(pdf.output())


def generer_recu(paiement, params):
    """Reçu remis au client après un remboursement."""
    pdf = PDF(params)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, _t("REÇU DE PAIEMENT"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(95, 7, _t(f"Reçu N° R-{paiement.id:05d}"))
    pdf.cell(95, 7, _t(f"Date : {paiement.date.strftime('%d/%m/%Y %H:%M')}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.titre_bandeau("CLIENT")
    pdf.cell(0, 6, _t(f"{paiement.client.nom} - {paiement.client.telephone or ''}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.titre_bandeau("DÉTAIL")
    d = paiement.dette
    if d:
        ref = f"Facture F-{d.vente_id:05d}" if d.vente_id else (d.description or f"Dette D-{d.id:05d}")
        pdf.ligne("Objet", f"Remboursement - {ref}")
        pdf.ligne("Montant initial de la dette", fmt_money(d.montant))
    pdf.ligne("Mode de paiement", paiement.mode or "-")
    pdf.set_fill_color(*BLEU_CLAIR)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(130, 10, _t("MONTANT REÇU"), fill=True)
    pdf.cell(60, 10, _t(fmt_money(paiement.montant)), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    if d:
        # reste après CE paiement (utile si on réimprime un ancien reçu)
        paye_jusque_la = sum(p.montant for p in d.paiements if p.date <= paiement.date)
        pdf.ligne("Reste à payer après ce paiement", fmt_money(max(d.montant - paye_jusque_la, 0)), gras=True)
    if paiement.note:
        pdf.ln(3)
        pdf.set_font("Helvetica", "I", 10)
        pdf.multi_cell(0, 6, _t(f"Note : {paiement.note}"))
    pdf.ln(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Édité le {datetime.now().strftime('%d/%m/%Y')} - Signature :"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
