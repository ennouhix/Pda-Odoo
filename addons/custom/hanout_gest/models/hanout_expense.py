# -*- coding: utf-8 -*-
"""Dépenses de caisse d'un magasin hanout."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HanoutExpense(models.Model):
    """Sortie d'espèces non marchande enregistrée pendant une session POS.

    Ces dépenses (transport, électricité, avance sur salaire…) sont déduites
    du théorique de caisse à la clôture de la session.
    """

    _name = 'hanout.expense'
    _description = "Dépense de caisse hanout"
    _order = 'date desc, id desc'

    name = fields.Char(
        string="Libellé",
        required=True,
        help="Motif de la dépense, par exemple « Livraison boissons ».",
    )
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    category = fields.Selection(
        selection=[
            ('supply', "Achat marchandise"),
            ('transport', "Transport"),
            ('utilities', "Électricité / eau"),
            ('rent', "Loyer"),
            ('salary', "Salaire / avance"),
            ('maintenance', "Entretien"),
            ('other', "Autre"),
        ],
        string="Catégorie",
        required=True,
        default='other',
    )
    amount = fields.Monetary(
        string="Montant",
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        string="Devise",
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    shop_id = fields.Many2one(
        comodel_name='hanout.shop',
        string="Magasin",
        domain="[('company_id', '=', company_id)]",
        ondelete='restrict',
        required=True,
        index=True,
        default=lambda self: self._default_shop_id(),
        help="Magasin dont la caisse a payé la dépense : chaque sortie "
             "d'espèces doit être imputée à un magasin.",
    )
    session_id = fields.Many2one(
        comodel_name='pos.session',
        string="Session de caisse",
        ondelete='set null',
        index=True,
        help="Session POS pendant laquelle la dépense a été engagée.",
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Saisi par",
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    note = fields.Text(
        string="Notes",
    )

    @api.model
    def _default_shop_id(self):
        """Pré-remplir le magasin quand la société n'en a qu'un."""
        shops = self.env['hanout.shop'].search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True),
        ], limit=2)
        return shops.id if len(shops) == 1 else False

    @api.constrains('shop_id', 'company_id')
    def _check_shop_company(self):
        """La dépense et son magasin doivent être dans la même société."""
        for expense in self:
            if expense.shop_id and expense.shop_id.company_id != expense.company_id:
                raise ValidationError(_(
                    "Le magasin %(shop)s n'appartient pas à la société de la "
                    "dépense.",
                    shop=expense.shop_id.display_name,
                ))

    @api.constrains('amount')
    def _check_amount(self):
        """Le montant d'une dépense doit être strictement positif."""
        for expense in self:
            if expense.amount <= 0:
                raise ValidationError(
                    _("Le montant d'une dépense doit être strictement positif.")
                )

    @api.constrains('session_id')
    def _check_session_state(self):
        """Interdire l'ajout d'une dépense à une session déjà clôturée."""
        for expense in self:
            if expense.session_id.state == 'closed':
                raise ValidationError(
                    _("Impossible d'ajouter une dépense à une session de "
                      "caisse déjà clôturée.")
                )

    @api.onchange('session_id')
    def _onchange_session_id(self):
        """Pré-remplir le magasin et la société depuis la session."""
        for expense in self:
            if not expense.session_id:
                continue
            expense.company_id = expense.session_id.company_id
            if not expense.shop_id:
                expense.shop_id = expense.session_id.config_id.hanout_shop_id
