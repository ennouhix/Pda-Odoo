#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère le guide fonctionnel PDF du module Hanout Gestion.

Usage :
    python3 scripts/build-hanout-guide.py [sortie.pdf]

Par défaut le fichier est écrit dans docs/HANOUT_GUIDE.pdf. Le script ne
dépend que de reportlab (installé avec Odoo) et des polices DejaVu.
"""
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


MODULE_VERSION = "19.0.1.2.0"
GREEN = colors.HexColor("#1c3f34")
GOLD = colors.HexColor("#b08a3e")
GREY = colors.HexColor("#5a5a5a")
LIGHT = colors.HexColor("#f2f0ea")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DejaVu", f"{FONT_DIR}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", f"{FONT_DIR}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Oblique", f"{FONT_DIR}/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont(
    "DejaVu-BoldOblique", f"{FONT_DIR}/DejaVuSans-BoldOblique.ttf"
))
pdfmetrics.registerFontFamily(
    "DejaVu",
    normal="DejaVu",
    bold="DejaVu-Bold",
    italic="DejaVu-Oblique",
    boldItalic="DejaVu-BoldOblique",
)

STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(
    "Couverture",
    fontName="DejaVu-Bold", fontSize=34, leading=40,
    textColor=GREEN, alignment=TA_CENTER, spaceAfter=6,
))
STYLES.add(ParagraphStyle(
    "CouvertureSous",
    fontName="DejaVu", fontSize=15, leading=20,
    textColor=GREY, alignment=TA_CENTER, spaceAfter=4,
))
STYLES.add(ParagraphStyle(
    "H1",
    fontName="DejaVu-Bold", fontSize=16, leading=21, textColor=GREEN,
    spaceBefore=16, spaceAfter=8, keepWithNext=True,
))
STYLES.add(ParagraphStyle(
    "H1HorsSommaire",
    parent=None, fontName="DejaVu-Bold", fontSize=16, leading=21,
    textColor=GREEN, spaceBefore=0, spaceAfter=8,
))
STYLES.add(ParagraphStyle(
    "H2",
    fontName="DejaVu-Bold", fontSize=12, leading=16, textColor=GOLD,
    spaceBefore=12, spaceAfter=5, keepWithNext=True,
))
STYLES.add(ParagraphStyle(
    "Corps",
    fontName="DejaVu", fontSize=9.3, leading=13.6,
    alignment=TA_JUSTIFY, spaceAfter=6,
))
STYLES.add(ParagraphStyle(
    "Puce",
    parent=STYLES["Corps"], leftIndent=13, bulletIndent=4,
    spaceAfter=3, alignment=0,
))
STYLES.add(ParagraphStyle(
    "Numero",
    parent=STYLES["Corps"], leftIndent=17, bulletIndent=2,
    spaceAfter=3, alignment=0,
))
STYLES.add(ParagraphStyle(
    "CorpsGauche",
    parent=STYLES["Corps"], alignment=0,
))
STYLES.add(ParagraphStyle(
    "Cellule",
    fontName="DejaVu", fontSize=8.3, leading=11.4,
))
STYLES.add(ParagraphStyle(
    "CelluleEntete",
    fontName="DejaVu-Bold", fontSize=8.3, leading=11.4,
    textColor=colors.white,
))
STYLES.add(ParagraphStyle(
    "Encart",
    fontName="DejaVu", fontSize=8.8, leading=12.6, textColor=GREY,
))
STYLES.add(ParagraphStyle(
    "TOC1",
    fontName="DejaVu-Bold", fontSize=9.2, leading=15, textColor=GREEN,
    rightIndent=6,
))
STYLES.add(ParagraphStyle(
    "TOCPage",
    fontName="DejaVu-Bold", fontSize=9.2, leading=15, alignment=2,
    textColor=GREEN,
))


class GuideDoc(BaseDocTemplate):
    """Document A4 avec pied de page et sommaire cliquable."""

    def __init__(self, filename, **kwargs):
        self.headings = []
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=2.1 * cm,
            rightMargin=2.1 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
            title="Hanout Gestion — Guide fonctionnel",
            author="Hanout Gestion",
            subject="Guide des fonctions du module Odoo 19 hanout_gest",
            **kwargs,
        )
        self._toc_seq = 0
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height, id="corps",
        )
        self.addPageTemplates([
            PageTemplate(id="couverture", frames=[frame]),
            PageTemplate(id="page", frames=[frame], onPage=self._pied_de_page),
        ])

    def _pied_de_page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(0.6)
        canvas.line(
            self.leftMargin, 1.55 * cm,
            A4[0] - self.rightMargin, 1.55 * cm,
        )
        canvas.setFont("DejaVu", 7.6)
        canvas.setFillColor(GREY)
        canvas.drawString(
            self.leftMargin, 1.15 * cm,
            f"Hanout Gestion — Guide fonctionnel (version {MODULE_VERSION})",
        )
        canvas.drawRightString(
            A4[0] - self.rightMargin, 1.15 * cm,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        if flowable.style.name not in ("H1", "H2"):
            return
        level = 0 if flowable.style.name == "H1" else 1
        text = flowable.getPlainText()
        # La clé du sommaire doit être une chaîne simple : reportlab
        # l'analyse pour retrouver l'entrée.
        self._toc_seq += 1
        key = f"SEC{level}_{self._toc_seq}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        # Le sommaire imprimé ne reprend que les sections ; les sous-titres
        # restent dans les signets du PDF.
        if level == 0:
            self.headings.append((text, self.page))


def h1(text):
    return Paragraph(text, STYLES["H1"])


def h2(text):
    return Paragraph(text, STYLES["H2"])


def p(text):
    return Paragraph(text, STYLES["Corps"])


def bullets(items):
    return [
        Paragraph(item, STYLES["Puce"], bulletText="•") for item in items
    ]


def numbered(items):
    return [
        Paragraph(item, STYLES["Numero"], bulletText=f"{index}.")
        for index, item in enumerate(items, 1)
    ]


def encart(text):
    table = Table(
        [[Paragraph(text, STYLES["Encart"])]],
        colWidths=[A4[0] - 4.2 * cm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([Spacer(1, 4), table, Spacer(1, 8)])


def table(header, rows, widths=None):
    data = [[Paragraph(cell, STYLES["CelluleEntete"]) for cell in header]]
    for row in rows:
        data.append([Paragraph(str(cell), STYLES["Cellule"]) for cell in row])
    total = A4[0] - 4.2 * cm
    table_object = Table(
        data,
        colWidths=widths or [total / len(header)] * len(header),
        repeatRows=1,
    )
    table_object.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfcabd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    # Les tableaux se coupent entre deux pages avec leur en-tête répété :
    # c'est plus dense qu'un bloc insécable qui laisserait des pages vides.
    table_object.spaceBefore = 5
    table_object.spaceAfter = 7
    return table_object


def couverture():
    story = [Spacer(1, 4.2 * cm)]
    story.append(Paragraph("HANOUT GESTION", STYLES["Couverture"]))
    story.append(Paragraph(
        "Guide fonctionnel du module Odoo 19", STYLES["CouvertureSous"],
    ))
    story.append(Paragraph(
        f"Version du module {MODULE_VERSION}", STYLES["CouvertureSous"],
    ))
    story.append(Spacer(1, 1.6 * cm))
    bande = Table([[""]], colWidths=[A4[0] - 4.2 * cm], rowHeights=[0.12 * cm])
    bande.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)]))
    story.append(bande)
    story.append(Spacer(1, 1.4 * cm))
    story.append(Paragraph(
        "Vendre, encaisser, noter les dépenses, clôturer la caisse, "
        "suivre le carnet de crédit : tout ce que le module ajoute à Odoo, "
        "écran par écran.",
        ParagraphStyle(
            "intro", parent=STYLES["CouvertureSous"], fontSize=11.5,
            leading=17, textColor=colors.black, alignment=TA_CENTER,
        ),
    ))
    story.append(Spacer(1, 12 * cm))
    story.append(Paragraph(
        f"Document généré le {date.today().strftime('%d/%m/%Y')} — "
        "modules hanout_gest et hanout_demo (licence LGPL-3).",
        ParagraphStyle(
            "pied", parent=STYLES["CouvertureSous"], fontSize=8.6,
        ),
    ))
    story.append(PageBreak())
    return story


def sommaire(entrees):
    """Sommaire imprimé : section à gauche, page à droite."""
    story = [
        # Le titre du sommaire n'entre pas dans le sommaire lui-même.
        Paragraph("Sommaire", STYLES["H1HorsSommaire"]),
    ]
    if entrees:
        largeur = A4[0] - 4.2 * cm
        lignes = [
            [Paragraph(titre, STYLES["TOC1"]), Paragraph(str(page), STYLES["TOCPage"])]
            for titre, page in entrees
        ]
        table_sommaire = Table(lignes, colWidths=[largeur - 1.6 * cm, 1.6 * cm])
        table_sommaire.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8d2c4")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(table_sommaire)
    story += [
        Spacer(1, 10),
        encart(
            "Ce guide décrit uniquement ce que le module Hanout Gestion "
            "ajoute à Odoo. La vente, le catalogue, le stock et la "
            "comptabilité restent ceux d'Odoo : le module ne duplique aucune "
            "de ces fonctions, il les simplifie pour une boutique de "
            "proximité."
        ),
        PageBreak(),
    ]
    return story


def presentation():
    story = [h1("1. Présentation")]
    story.append(p(
        "Hanout Gestion est une couche métier posée sur Odoo 19 Community. "
        "Elle répond à un besoin précis : une épicerie de quartier où un "
        "caissier peu formé doit vendre vite, où le gérant doit retrouver "
        "chaque dirham, et où les clients achètent souvent à crédit sur un "
        "carnet."
    ))
    story.append(h2("Ce que le module apporte"))
    story += bullets([
        "Des <b>magasins</b> hanout, chacun avec son entrepôt, ses caisses "
        "et sa numérotation de tickets propre.",
        "Une <b>caisse simplifiée</b> : grandes tuiles produits, gros bouton "
        "d'encaissement, actions avancées masquées.",
        "Un <b>ticket de caisse hanout</b> à l'identité du magasin, numéroté "
        "par magasin.",
        "Les <b>dépenses de caisse</b> du jour (transport, électricité, "
        "avance sur salaire…), déduites du théorique avant clôture.",
        "Une <b>clôture journalière</b> lisible, avec écart de comptage "
        "calculé sur le bon théorique.",
        "Un <b>carnet de crédit client</b> : plafond, solde, écran des "
        "débiteurs et règlements partiels, sur la comptabilité native.",
        "Deux <b>rôles</b> prêts à l'emploi : caissier et gérant.",
    ])
    story.append(h2("Ce que le module ne remplace pas"))
    story.append(p(
        "La vente, le catalogue, les stocks, les paiements et la "
        "comptabilité restent ceux d'Odoo. Les données produites par le "
        "module sont des données Odoo standard : tickets POS, sessions de "
        "caisse, créances clients, écritures comptables. Aucun journal de "
        "dettes « maison » n'est tenu à côté de la comptabilité."
    ))
    story.append(h2("Public visé"))
    story.append(table(
        ["Rôle", "Ce qu'il fait dans le module"],
        [
            ["Caissier", "Vend, encaisse (espèces ou carnet), saisit les "
                         "dépenses du jour, ferme sa caisse."],
            ["Gérant", "Configure magasins et caisses, contrôle et corrige "
                       "les dépenses, suit et encaisse les dettes."],
            ["Administrateur", "Installe, met à jour, gère la comptabilité et "
                               "les utilisateurs."],
        ],
        [3.4 * cm, (A4[0] - 4.2 * cm) - 3.4 * cm],
    ))
    return story


def installation():
    story = [h1("2. Installation et mise en route")]
    story.append(h2("Prérequis"))
    story.append(p(
        "Odoo 19 Community avec les modules Point de Vente et Inventaire, "
        "un plan comptable installé et une devise configurée (MAD dans la "
        "base de démonstration)."
    ))
    story.append(h2("Installer le module"))
    story.append(encart(
        "docker compose up -d<br/>"
        "docker compose run --rm odoo odoo -d ma_base -i hanout_gest "
        "--stop-after-init"
    ))
    story.append(p(
        "Pour une base de démonstration prête à l'emploi (magasin, caisse, "
        "catalogue, comptes de test, client carnet), installer aussi "
        "<b>hanout_demo</b> :"
    ))
    story.append(encart(
        "docker compose run --rm odoo odoo -d hanout_dev -i hanout_demo "
        "--stop-after-init"
    ))
    story.append(h2("Comptes de démonstration"))
    story.append(table(
        ["Compte", "Identifiant", "Mot de passe"],
        [
            ["Caissier Hanout", "hanout.caissier", "hanout.caissier"],
            ["Gérant Hanout", "hanout.gerant", "hanout.gerant"],
            ["Administrateur", "admin", "admin"],
        ],
        [5 * cm, 6 * cm, (A4[0] - 4.2 * cm) - 11 * cm],
    ))
    story.append(h2("Préparer une caisse en quatre étapes"))
    story += numbered([
        "Créer le magasin dans <b>Hanout &gt; Configuration &gt; Magasins</b> : "
        "nom, code court, entrepôt, téléphone et adresse (ces deux derniers "
        "s'impriment sur le ticket).",
        "Affecter les utilisateurs aux groupes <b>Caissier Hanout</b> ou "
        "<b>Gérant Hanout</b>.",
        "Ouvrir la caisse dans <b>Hanout &gt; Configuration &gt; Caisses</b>, "
        "choisir son <b>Magasin hanout</b> et vérifier qu'un moyen de "
        "paiement en espèces est présent.",
        "Cliquer <b>Appliquer le mode hanout simple</b> : la caisse est réglée "
        "pour un caissier débutant et reçoit le moyen de paiement <b>Crédit "
        "carnet</b>.",
    ])
    story.append(encart(
        "Le mode hanout ne modifie les moyens de paiement que caisse fermée. "
        "Si une session est ouverte, le bouton l'indique : fermez la caisse, "
        "appliquez le mode, puis rouvrez-la."
    ))
    return story


def menus():
    story = [h1("3. Organisation des menus")]
    story.append(p(
        "Tout est regroupé sous un menu unique <b>Hanout</b>, dans l'ordre "
        "du travail quotidien : vendre d'abord, le reste ensuite."
    ))
    story.append(table(
        ["Menu", "Contenu"],
        [
            ["Hanout &gt; Vendre", "Ouvre le tableau de bord des caisses "
                                   "rattachées à un magasin ; un clic sur "
                                   "<b>Open Register</b> démarre la session."],
            ["Hanout &gt; Caisse &gt; Sessions", "Sessions de caisse : "
                                                "ouverture, suivi, clôture, "
                                                "onglet « Clôture hanout »."],
            ["Hanout &gt; Caisse &gt; Dépenses", "Dépenses du jour, avec le "
                                                "total et le filtre du jour "
                                                "activé par défaut."],
            ["Hanout &gt; Carnet &gt; Débiteurs", "Clients qui doivent "
                                                 "encore de l'argent."],
            ["Hanout &gt; Magasins", "Fiches magasins (liste et formulaire)."],
            ["Hanout &gt; Configuration", "Réservé au gérant : magasins et "
                                          "caisses."],
        ],
        [6.2 * cm, (A4[0] - 4.2 * cm) - 6.2 * cm],
    ))
    story.append(p(
        "Le bouton <b>Ouvrir la caisse</b> existe aussi à trois endroits, "
        "pour ne jamais chercher : fiche du magasin, fiche de la caisse, et "
        "ligne de la liste des caisses."
    ))
    return story


def magasins():
    story = [h1("4. Les magasins")]
    story.append(p(
        "Un magasin hanout est le point de rattachement de tout le reste : "
        "il porte l'entrepôt de stock, les caisses, la numérotation des "
        "tickets et l'identité imprimée sur le ticket."
    ))
    story.append(h2("Fiche magasin"))
    story.append(table(
        ["Champ", "Rôle"],
        [
            ["Nom", "Nom affiché sur le ticket, en majuscules."],
            ["Code", "Code court unique par société (HCS, H1…). Il sert de "
                     "préfixe à la numérotation des tickets."],
            ["Société", "Société propriétaire ; le magasin n'est visible que "
                        "par ses utilisateurs."],
            ["Entrepôt", "Entrepôt dont le stock alimente le magasin."],
            ["Téléphone / Adresse", "Coordonnées imprimées sur le ticket."],
            ["Caisses", "Caisses Point de Vente rattachées au magasin."],
            ["Notes", "Informations libres pour l'équipe."],
        ],
        [4.2 * cm, (A4[0] - 4.2 * cm) - 4.2 * cm],
    ))
    story.append(h2("Numérotation des tickets"))
    story.append(p(
        "Chaque magasin reçoit automatiquement une séquence de tickets de la "
        "forme <b>CODE/ANNÉE/NUMÉRO</b>, par exemple <b>HCS/2026/000042</b>, "
        "avec un compteur sur six chiffres. Toutes les caisses du magasin "
        "partagent cette séquence : la numérotation est donc continue d'une "
        "caisse à l'autre, et un ticket identifie le magasin, pas la caisse. "
        "Changer le code du magasin met à jour le préfixe des tickets "
        "suivants."
    ))
    story.append(h2("Cloisonnement par société"))
    story.append(p(
        "Les magasins et les dépenses sont filtrés par société : un "
        "utilisateur ne voit que les siens, même avec une recherche vide. "
        "Une caisse et son magasin, comme une dépense et son magasin, "
        "doivent appartenir à la même société : le module refuse le "
        "contraire avec un message explicite."
    ))
    story.append(h2("Ouvrir la caisse depuis le magasin"))
    story.append(p(
        "Le bouton <b>Ouvrir la caisse</b> de la fiche magasin démarre "
        "directement la caisse quand le magasin n'en a qu'une. S'il en a "
        "plusieurs, Odoo propose de choisir laquelle ouvrir. Un magasin sans "
        "caisse affiche un message qui explique quoi faire plutôt qu'une "
        "erreur technique."
    ))
    return story


def caisse():
    story = [h1("5. La caisse")]
    story.append(p(
        "Une caisse hanout est une caisse Point de Vente Odoo ordinaire, à "
        "laquelle s'ajoutent un magasin et un mode d'affichage simplifié."
    ))
    story.append(h2("Réglages ajoutés"))
    story.append(table(
        ["Réglage", "Effet"],
        [
            ["Magasin hanout", "Rattache la caisse à un magasin : dépenses, "
                               "clôture et numérotation des tickets en "
                               "découlent. Obligatoire dès que le mode "
                               "simplifié est actif."],
            ["Mode hanout simplifié", "Active l'interface de caisse épurée. "
                                      "Il s'active tout seul quand la caisse "
                                      "reçoit un magasin."],
            ["Bouton « Appliquer le mode hanout simple »", "Règle la caisse "
                                                           "en une fois "
                                                           "(voir ci-dessous)."],
        ],
        [4.8 * cm, (A4[0] - 4.2 * cm) - 4.8 * cm],
    ))
    story.append(h2("Ce que fait « Appliquer le mode hanout simple »"))
    story += bullets([
        "Active le mode simplifié et agrandit les tuiles produits et "
        "catégories.",
        "Coupe les remises manuelles, les pourboires, les listes de prix et "
        "le mode restaurant.",
        "Branche le paiement rapide sur le moyen de paiement en espèces : un "
        "clic encaisse.",
        "Ajoute à la caisse le moyen de paiement <b>Crédit carnet</b> "
        "(créé au besoin).",
        "Rappelle qu'une caisse doit être fermée pour être modifiée.",
    ])
    story.append(h2("L'interface simplifiée"))
    story.append(p(
        "Le mode simplifié pose une classe sur l'écran de caisse et masque "
        "tout ce qui n'est pas utile au comptoir :"
    ))
    story.append(table(
        ["Masqué", "Conservé"],
        [
            ["Pavé quantité / prix / remise", "Tuiles produits et catégories "
                                              "en grand format"],
            ["Bouton historique des tickets", "Bouton « Payer » et paiement "
                                              "rapide espèces, en gros"],
            ["Client, note, liste de prix, annulation",
             "Bouton « Autres actions », limité au retour client"],
            ["Raccourcis de barre supérieure",
             "Recherche produit, scan code-barres, menu"],
        ],
        [7.6 * cm, (A4[0] - 4.2 * cm) - 7.6 * cm],
    ))
    story.append(h2("Retour client"))
    story.append(p(
        "Un client rapporte un article : le caissier ouvre <b>Autres "
        "actions</b>, puis <b>Retour</b>. C'est la seule action avancée "
        "conservée en mode simplifié ; l'annulation de commande, la note "
        "client et la liste de prix restent masquées. Le retour crée un "
        "ticket négatif, avec les mêmes produits et la même numérotation."
    ))
    return story


def vendre():
    story = [h1("6. Vendre au quotidien")]
    story.append(h2("Déroulé d'une vente"))
    story += numbered([
        "Le caissier ouvre sa session depuis <b>Hanout &gt; Vendre</b> (ou "
        "<b>Ouvrir la caisse</b>).",
        "Il touche les produits : ils s'ajoutent au ticket.",
        "Il touche <b>Payer</b>, puis encaisse en espèces (un clic avec le "
        "paiement rapide) ou avec le moyen de paiement <b>Crédit carnet</b> "
        "après avoir choisi le client.",
        "Le ticket s'imprime avec le numéro du magasin.",
    ])
    story.append(h2("Numéro de ticket"))
    story.append(p(
        "Le numéro imprimé est celui du magasin : <b>HCS/2026/000042</b>. Il "
        "reste lisible dans Odoo sur la commande de caisse, et il est unique "
        "par magasin et par année. Le numéro technique interne d'Odoo n'est "
        "pas imprimé."
    ))
    story.append(h2("Le ticket imprimé"))
    story.append(table(
        ["Bloc", "Contenu en mode simplifié"],
        [
            ["En-tête", "Bandeau zellige, nom du magasin en majuscules, "
                        "séparateur, adresse et téléphone."],
            ["Ticket", "Numéro, date, caissier, détail des articles avec "
                       "quantités et prix."],
            ["Totaux", "Total en bloc inversé, liste des paiements et monnaie "
                       "rendue."],
            ["Pied", "Remerciements bilingues arabes/français et « À bientôt, "
                     "inchallah »."],
            ["Retiré", "Logo société, QR « besoin d'une facture », mention "
                       "Odoo."],
        ],
        [3.4 * cm, (A4[0] - 4.2 * cm) - 3.4 * cm],
    ))
    story.append(encart(
        "Hors mode simplifié, le ticket reste celui d'Odoo : logo, QR de "
        "facture et mention Odoo reviennent. C'est voulu : le gérant peut "
        "ainsi produire un ticket standard quand la situation l'exige."
    ))
    return story


def depenses():
    story = [h1("7. Les dépenses de caisse")]
    story.append(p(
        "L'argent qui sort de la caisse sans être une vente est enregistré "
        "comme dépense hanout. Sans cela, la caisse semblerait manquer "
        "d'espèces à la clôture."
    ))
    story.append(h2("Champs d'une dépense"))
    story.append(table(
        ["Champ", "Rôle"],
        [
            ["Libellé", "Motif, par exemple « Livraison boissons »."],
            ["Catégorie", "Nature de la dépense (voir la liste ci-dessous)."],
            ["Montant", "Strictement positif, dans la devise de la société."],
            ["Date", "Date de la sortie d'espèces, aujourd'hui par défaut."],
            ["Magasin", "Obligatoire : chaque dépense est imputée à un "
                        "magasin. Pré-rempli si la société n'en a qu'un."],
            ["Session de caisse", "Session pendant laquelle la dépense a été "
                                  "engagée ; la déduction à la clôture en "
                                  "découle."],
            ["Saisi par", "Utilisateur qui a enregistré la dépense."],
        ],
        [4.2 * cm, (A4[0] - 4.2 * cm) - 4.2 * cm],
    ))
    story.append(h2("Catégories"))
    story.append(table(
        ["Catégorie", "Usage typique"],
        [
            ["Achat marchandise", "Payé au fournisseur ou au livreur."],
            ["Transport", "Livraison, taxi, carburant."],
            ["Électricité / eau", "Factures du local."],
            ["Loyer", "Loyer du mois."],
            ["Salaire / avance", "Avance versée à un employé."],
            ["Entretien", "Petites réparations, produits d'entretien."],
            ["Autre", "Tout ce qui ne rentre pas ailleurs."],
        ],
        [5 * cm, (A4[0] - 4.2 * cm) - 5 * cm],
    ))
    story.append(h2("Règles appliquées"))
    story += bullets([
        "Une dépense ne peut pas être rattachée à une session déjà "
        "clôturée.",
        "Le montant doit être strictement positif.",
        "La dépense et son magasin doivent appartenir à la même société.",
        "Une dépense n'est supprimable que par un gérant ; un caissier peut "
        "en saisir et en corriger.",
    ])
    story.append(h2("Où les retrouver"))
    story.append(p(
        "Dans <b>Hanout &gt; Caisse &gt; Dépenses</b>, avec le filtre "
        "« Aujourd'hui » actif et le total en pied de liste, groupable par "
        "catégorie, magasin, session ou date. Sur une session, le bouton "
        "d'état affiche le total des dépenses et l'onglet <b>Clôture "
        "hanout</b> les liste."
    ))
    return story


def cloture():
    story = [h1("8. Clôture journalière")]
    story.append(p(
        "Odoo calcule un théorique de caisse à partir des espèces encaissées. "
        "Dans un hanout, de l'argent est aussi sorti pour le transport ou "
        "l'électricité : le module déduit les dépenses du jour de ce "
        "théorique, pour que l'écart affiché soit le vrai écart."
    ))
    story.append(h2("Ce que montre l'onglet « Clôture hanout »"))
    story.append(table(
        ["Ligne", "Signification"],
        [
            ["Magasin", "Magasin de la session."],
            ["Fond de caisse", "Espèces présentes à l'ouverture."],
            ["Total des dépenses", "Somme des dépenses de la session."],
            ["Théorique de caisse", "Encaissements espèces moins dépenses."],
            ["Comptage", "Montant réellement compté par le caissier."],
            ["Écart", "Comptage moins théorique : positif = excédent, "
                      "négatif = manquant."],
        ],
        [5 * cm, (A4[0] - 4.2 * cm) - 5 * cm],
    ))
    story.append(h2("Exemple"))
    story.append(p(
        "Fond de caisse 100, ventes espèces 400, dépenses 80 : théorique = "
        "100 + 400 − 80 = 420. Si le caissier compte 415, l'écart est de −5 "
        "(manquant de 5), et non de +75 comme le montrerait un théorique "
        "sans les dépenses."
    ))
    story.append(h2("Déroulé de la clôture"))
    story.append(p(
        "Le caissier ouvre <b>Hanout &gt; Caisse &gt; Sessions</b>, ouvre sa "
        "session, vérifie l'onglet <b>Clôture hanout</b>, saisit le montant "
        "compté puis ferme la caisse. Si un oubli apparaît, une dépense peut "
        "encore être ajoutée avant la fermeture — jamais après."
    ))
    return story


def carnet():
    story = [h1("9. Le carnet de crédit")]
    story.append(p(
        "Le carnet s'appuie sur Odoo : une vente payée avec le moyen de "
        "paiement <b>Crédit carnet</b> crée une créance au nom du client dans "
        "la comptabilité. Le module ajoute le plafond, le solde en temps "
        "réel, l'écran des débiteurs et le règlement partiel."
    ))
    story.append(h2("Le moyen de paiement « Crédit carnet »"))
    story.append(p(
        "C'est un moyen de paiement de type <b>compte client</b> : aucun "
        "journal, donc aucun mouvement de trésorerie, et l'option "
        "<b>Identify Customer</b> activée. Le bouton « Appliquer le mode "
        "hanout simple » le crée, ou réutilise le moyen natif « Customer "
        "Account » s'il existe déjà avec cette option. Sans cette option, la "
        "créance tomberait sur un compte d'attente anonyme et aucun solde ne "
        "serait suivi."
    ))
    story.append(h2("Plafond et soldes sur la fiche client"))
    story.append(table(
        ["Champ", "Signification"],
        [
            ["Plafond du carnet", "Montant maximum accordé. Zéro = carnet "
                                  "illimité."],
            ["Solde du carnet", "Créances comptables ouvertes : ce que le "
                                "client doit d'après la comptabilité."],
            ["Crédit en session", "Ventes à crédit d'une caisse encore "
                                  "ouverte, pas encore comptabilisées."],
            ["Crédit disponible", "Plafond moins solde moins crédit en "
                                  "session. Reste à zéro si aucun plafond "
                                  "n'est fixé."],
        ],
        [4.6 * cm, (A4[0] - 4.2 * cm) - 4.6 * cm],
    ))
    story.append(h2("Ce qui est refusé"))
    story.append(table(
        ["Situation", "Comportement"],
        [
            ["Vente à crédit sans client", "Refusée : le carnet ne peut pas "
                                           "être anonyme."],
            ["Vente qui dépasse le plafond",
             "Refusée avant enregistrement du paiement : rien n'est laissé "
             "en base. Le message donne le solde qui serait atteint, le "
             "plafond et la solution (encaisser une partie, régler le "
             "carnet)."],
            ["Client sans plafond", "Accepté : carnet illimité."],
            ["Retour client (montant négatif)", "Accepté : il réduit le "
                                                "carnet."],
        ],
        [6 * cm, (A4[0] - 4.2 * cm) - 6 * cm],
    ))
    story.append(p(
        "Le contrôle tient compte du crédit de la session en cours, pas "
        "seulement de la comptabilité déjà passée : un client ne peut donc "
        "pas dépasser son plafond deux fois dans la même journée."
    ))
    story.append(h2("L'écran des débiteurs"))
    story.append(p(
        "<b>Hanout &gt; Carnet &gt; Débiteurs</b> liste les clients dont le "
        "carnet n'est pas soldé, avec le total dû en pied de liste, le "
        "téléphone, le plafond et le crédit disponible. Chaque ligne porte un "
        "bouton pour encaisser un règlement."
    ))
    story.append(h2("Encaisser un règlement, même partiel"))
    story.append(p(
        "Depuis la fiche client (bouton <b>Règlement carnet</b>) ou depuis la "
        "liste des débiteurs : le module propose le solde dû, le caissier "
        "choisit le journal (caisse du magasin ou banque), la date, le "
        "montant reçu et une référence. Un paiement comptable est enregistré "
        "puis lettré avec les créances ouvertes, de la plus ancienne à la "
        "plus récente. Un acompte de 25 sur une dette de 40 laisse donc 15."
    ))
    story.append(p(
        "Un règlement nul ou supérieur au solde est refusé : inutile de "
        "créer un crédit client pour un trop-perçu."
    ))
    story.append(encart(
        "Le crédit d'une session encore ouverte n'existe pas en "
        "comptabilité : il n'apparaît ni dans les débiteurs ni dans le solde "
        "réglable avant la clôture de la caisse. C'est la limite assumée du "
        "lot ; le caissier voit ce montant dans « Crédit en session »."
    ))
    return story


def droits():
    story = [h1("10. Droits et groupes")]
    story.append(table(
        ["Groupe", "Droits"],
        [
            ["Caissier Hanout",
             "Vend en caisse, saisit et corrige les dépenses, consulte les "
             "magasins, encaisse les règlements de carnet, ferme sa propre "
             "session. Ne peut pas supprimer une dépense ni configurer une "
             "caisse."],
            ["Gérant Hanout",
             "Tout le caissier, plus la configuration des magasins et des "
             "caisses et la suppression des dépenses. Voit le crédit "
             "disponible des clients."],
        ],
        [4 * cm, (A4[0] - 4.2 * cm) - 4 * cm],
    ))
    story.append(p(
        "Les deux groupes héritent des droits Point de Vente d'Odoo et sont "
        "visibles dans la fiche utilisateur, catégorie <b>Hanout</b>. Le menu "
        "Configuration n'apparaît qu'au gérant."
    ))
    return story


def technique():
    story = [h1("11. Fonctionnement technique")]
    story.append(p(
        "Cette section résume ce que le module stocke et où, pour un "
        "administrateur ou un développeur qui reprend l'installation."
    ))
    story.append(h2("Objets ajoutés"))
    story.append(table(
        ["Objet", "Contenu"],
        [
            ["hanout.shop", "Magasin : nom, code, société, entrepôt, "
                            "coordonnées, séquence de ticket, caisses."],
            ["hanout.expense", "Dépense de caisse : libellé, catégorie, "
                               "montant, date, magasin, session, auteur."],
            ["hanout.credit.payment", "Formulaire de règlement du carnet "
                                      "(client, montant, journal, date)."],
        ],
        [4.6 * cm, (A4[0] - 4.2 * cm) - 4.6 * cm],
    ))
    story.append(h2("Extensions de l'existant"))
    story.append(table(
        ["Modèle Odoo", "Ajout"],
        [
            ["pos.config", "Magasin hanout, mode simplifié, moyen de "
                           "paiement carnet, bouton de préparation."],
            ["pos.session", "Magasin, dépenses de la session, total, "
                            "théorique ajusté, onglet de clôture."],
            ["pos.order", "Nom du ticket au format magasin/année/numéro."],
            ["pos.payment", "Contrôle du plafond du carnet avant "
                            "enregistrement."],
            ["res.partner", "Plafond, solde, crédit en session, crédit "
                            "disponible, bouton de règlement."],
        ],
        [3.6 * cm, (A4[0] - 4.2 * cm) - 3.6 * cm],
    ))
    story.append(h2("Règles et contrôles"))
    story += bullets([
        "Deux règles d'enregistrement limitent magasins et dépenses aux "
        "sociétés de l'utilisateur.",
        "Le magasin d'une caisse et d'une dépense doit être celui de sa "
        "société.",
        "Une caisse en mode simplifié doit avoir un magasin ; une caisse "
        "Point de Vente classique reste possible.",
        "La numérotation des tickets est une séquence Odoo par magasin, "
        "partagée par ses caisses.",
        "Les données existantes sont reprises par deux migrations : création "
        "des séquences de ticket, puis assouplissement du magasin de caisse "
        "avec remise à zéro des caisses non hanout.",
    ])
    story.append(h2("Interface de caisse"))
    story.append(p(
        "Le mode simplifié est une classe posée sur l'écran de caisse quand "
        "la caisse est en mode hanout, complétée par une feuille de style qui "
        "masque pavé, actions et raccourcis et agrandit les cibles tactiles. "
        "Le retour client est marqué dans le gabarit de la fenêtre « Autres "
        "actions »."
    ))
    story.append(h2("Tests"))
    story.append(p(
        "La suite couvre la création des magasins et des séquences, la "
        "numérotation des tickets, l'ouverture de caisse, les dépenses et "
        "leur effet sur le théorique, le cloisonnement par société, les "
        "règles du carnet et son règlement partiel."
    ))
    story.append(encart(
        "docker compose run --rm odoo odoo -d hanout_dev -u hanout_gest "
        "--test-tags /hanout_gest --stop-after-init<br/><br/>"
        "31 tests, 0 échec sur la base de démonstration."
    ))
    return story


def limites():
    story = [h1("12. Limites connues et suite")]
    story.append(h2("Limites de cette version"))
    story += bullets([
        "Le dépassement de plafond est refusé au moment où le ticket est "
        "enregistré, avec le message Odoo standard : il n'y a pas encore de "
        "contrôle dans l'écran de caisse avant la validation.",
        "Le crédit d'une session encore ouverte ne peut pas être réglé avant "
        "la clôture de la caisse.",
        "Pas encore de rapport dédié : ventes, dépenses et dettes se lisent "
        "dans les vues et analyses standard d'Odoo.",
        "Un seul entrepôt par magasin, pas de gestion de lots ni de "
        "numéros de série dans l'interface simplifiée.",
    ])
    story.append(h2("Suite prévue"))
    story.append(table(
        ["Lot", "Contenu"],
        [
            ["3", "Alertes de rupture en caisse, réapprovisionnement et "
                  "inventaire rapide par scan."],
            ["4", "Achats fournisseurs et réception guidée."],
            ["5", "Tableau de bord gérant : chiffre d'affaires, marge, top "
                  "produits, dettes."],
            ["6", "Industrialisation : sauvegardes, mises à jour, formation "
                  "caissier."],
        ],
        [2 * cm, (A4[0] - 4.2 * cm) - 2 * cm],
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Documentation complémentaire : <b>addons/custom/hanout_gest/"
        "README.md</b> (référence du module) et <b>README.md</b> à la racine "
        "du dépôt (installation de la démonstration).",
        STYLES["CorpsGauche"],
    ))
    return story


def corps(entrees):
    """Contenu complet du guide, sommaire inclus."""
    story = []
    story += couverture()
    story += sommaire(entrees)
    for section in (
        presentation(), installation(), menus(), magasins(), caisse(),
        vendre(), depenses(), cloture(), carnet(), droits(), technique(),
        limites(),
    ):
        story += section
    return story


def build(path):
    # Le sommaire occupe sa propre page : la première passe relève les numéros
    # de page des sections, la seconde les imprime sans rien décaler.
    premier = GuideDoc(path)
    premier.build(corps([]))
    entrees = premier.headings
    GuideDoc(path).build(corps(entrees))
    return path


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "docs/HANOUT_GUIDE.pdf"
    print(f"Guide écrit : {build(output)}")
