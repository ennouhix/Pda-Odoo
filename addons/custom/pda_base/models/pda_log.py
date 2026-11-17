# -*- coding: utf-8 -*-
"""Journal des opérations effectuées depuis l'application PDA."""
from odoo import fields, models


class PdaLog(models.Model):
    """Ligne de journal retraçant un appel ou une opération PDA."""

    _name = 'pda.log'
    _description = "Journal des opérations PDA"
    _order = 'date desc, id desc'
    _rec_name = 'operation'

    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Utilisateur",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='restrict',
        readonly=True,
        help="Utilisateur à l'origine de l'opération.",
    )
    date = fields.Datetime(
        string="Date",
        required=True,
        default=fields.Datetime.now,
        index=True,
        readonly=True,
    )
    operation = fields.Selection(
        selection=[
            ('lookup', "Recherche"),
            ('receipt', "Réception"),
            ('issue', "Sortie"),
            ('transfer', "Transfert"),
            ('inventory', "Inventaire"),
        ],
        string="Opération",
        required=True,
        index=True,
        readonly=True,
    )
    barcode = fields.Char(
        string="Code-barres",
        index=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Produit",
        ondelete='set null',
        index=True,
        readonly=True,
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string="Emplacement source",
        ondelete='set null',
        readonly=True,
    )
    location_dest_id = fields.Many2one(
        comodel_name='stock.location',
        string="Emplacement destination",
        ondelete='set null',
        readonly=True,
    )
    quantity = fields.Float(
        string="Quantité",
        digits='Product Unit',
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('success', "Succès"),
            ('error', "Erreur"),
        ],
        string="État",
        required=True,
        default='success',
        index=True,
        readonly=True,
    )
    message = fields.Text(
        string="Message",
        readonly=True,
    )
