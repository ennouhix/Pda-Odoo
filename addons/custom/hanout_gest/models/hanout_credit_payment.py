# -*- coding: utf-8 -*-
"""Règlement (partiel) du carnet de crédit d'un client."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HanoutCreditPayment(models.TransientModel):
    """Encaisser un règlement du carnet et le lettrer avec les créances.

    Le caissier saisit le montant remis par le client : un paiement comptable
    est enregistré dans le journal choisi (caisse du magasin ou banque) puis
    réconcilié avec les créances ouvertes du client, de la plus ancienne à la
    plus récente. Un client peut donc payer une partie de sa dette.
    """

    _name = 'hanout.credit.payment'
    _description = "Règlement du carnet hanout"

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Client",
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        string="Devise",
        readonly=True,
    )
    balance = fields.Monetary(
        string="Solde du carnet",
        currency_field='currency_id',
        compute='_compute_balance',
        help="Créances comptables ouvertes du client.",
    )
    pending = fields.Monetary(
        string="Crédit en session",
        currency_field='currency_id',
        compute='_compute_balance',
        help="Ventes à crédit d'une session encore ouverte : elles ne peuvent "
             "être réglées qu'après la clôture de la caisse.",
    )
    amount = fields.Monetary(
        string="Montant reçu",
        currency_field='currency_id',
        required=True,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Journal",
        required=True,
        domain="[('type', 'in', ('cash', 'bank')), ('company_id', '=', company_id)]",
        help="Caisse du magasin pour un règlement en espèces, banque pour un "
             "virement ou un chèque.",
    )
    payment_date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
    )
    reference = fields.Char(
        string="Référence",
        help="Précision portée sur le paiement, par exemple « acompte ».",
    )

    @api.depends('partner_id')
    def _compute_balance(self):
        for wizard in self:
            wizard.balance = wizard.partner_id.hanout_credit_balance
            wizard.pending = wizard.partner_id.hanout_credit_pending

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        """Pré-remplir le montant et le journal d'espèces du magasin."""
        for wizard in self:
            wizard.amount = max(wizard.partner_id.hanout_credit_balance, 0.0)
            if not wizard.journal_id:
                wizard.journal_id = self.env['account.journal'].search([
                    ('type', '=', 'cash'),
                    ('company_id', '=', wizard.company_id.id),
                ], limit=1)

    def action_register(self):
        """Enregistrer le paiement puis lettrer les créances du client."""
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Le montant reçu doit être positif."))
        balance = self.partner_id.hanout_credit_balance
        if self.amount > balance:
            raise UserError(_(
                "Le montant reçu (%(amount)s) dépasse le solde du carnet de "
                "%(partner)s (%(balance)s).",
                amount=self.amount,
                partner=self.partner_id.display_name,
                balance=balance,
            ))
        payment = self.env['account.payment'].sudo().create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'journal_id': self.journal_id.id,
            'date': self.payment_date,
            'memo': self.reference or _("Règlement carnet"),
            'company_id': self.company_id.id,
        })
        payment.action_post()
        self._reconcile_open_debts(payment)
        self.partner_id.invalidate_recordset()
        remaining = self.partner_id.hanout_credit_balance
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Règlement enregistré"),
                'message': _(
                    "%(amount)s encaissés pour %(partner)s. Reste à payer : "
                    "%(remaining)s.",
                    amount=self.amount,
                    partner=self.partner_id.display_name,
                    remaining=remaining,
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _reconcile_open_debts(self, payment):
        """Lettrer le paiement avec les créances ouvertes, plus anciennes d'abord."""
        receivable_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        )
        if not receivable_lines:
            raise UserError(_(
                "Le journal %(journal)s ne produit pas de ligne client : "
                "choisissez un autre journal.",
                journal=self.journal_id.display_name,
            ))
        open_debts = self.env['account.move.line'].search([
            ('partner_id', '=', self.partner_id.id),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('id', 'not in', receivable_lines.ids),
        ], order='date, id')
        (receivable_lines | open_debts).reconcile()
