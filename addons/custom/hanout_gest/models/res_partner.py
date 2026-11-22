# -*- coding: utf-8 -*-
"""Carnet de crédit des clients hanout.

Le crédit s'appuie sur le moyen de paiement natif « Customer Account »
(``pay_later``) d'Odoo : la vente à crédit produit une créance au nom du
client dans la comptabilité. Ce fichier ajoute ce qui manque au hanout :
le plafond du carnet, le solde dû en temps réel et le règlement partiel.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

OPERATORS = {
    '=': lambda left, right: left == right,
    '!=': lambda left, right: left != right,
    '>': lambda left, right: left > right,
    '>=': lambda left, right: left >= right,
    '<': lambda left, right: left < right,
    '<=': lambda left, right: left <= right,
}


class ResPartner(models.Model):
    """Plafond et solde du carnet de crédit."""

    _inherit = 'res.partner'

    hanout_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Devise du carnet",
        compute='_compute_hanout_currency_id',
        help="Devise de la société du client, utilisée pour le carnet.",
    )
    hanout_credit_limit = fields.Monetary(
        string="Plafond du carnet",
        currency_field='hanout_currency_id',
        help="Montant maximum de crédit accordé au client. Laisser à zéro "
             "pour autoriser le carnet sans plafond.",
    )
    hanout_credit_balance = fields.Monetary(
        string="Solde du carnet",
        currency_field='hanout_currency_id',
        compute='_compute_hanout_credit_balance',
        search='_search_hanout_credit_balance',
        help="Ce que le client doit encore, d'après les créances comptables "
             "ouvertes. Les ventes à crédit d'une session de caisse encore "
             "ouverte ne sont comptabilisées qu'à sa clôture.",
    )
    hanout_credit_pending = fields.Monetary(
        string="Crédit en session",
        currency_field='hanout_currency_id',
        compute='_compute_hanout_credit_balance',
        help="Ventes à crédit de sessions de caisse encore ouvertes : elles "
             "comptent dans le plafond mais pas encore dans la comptabilité.",
    )
    hanout_credit_available = fields.Monetary(
        string="Crédit disponible",
        currency_field='hanout_currency_id',
        compute='_compute_hanout_credit_balance',
        help="Plafond diminué du solde du carnet. Sans plafond, ce champ "
             "reste à zéro : le carnet est illimité.",
    )

    @api.depends('company_id')
    def _compute_hanout_currency_id(self):
        for partner in self:
            company = partner.company_id or self.env.company
            partner.hanout_currency_id = company.currency_id

    @api.depends('hanout_credit_limit')
    def _compute_hanout_credit_balance(self):
        balances = self._hanout_credit_balances()
        pending = self._hanout_credit_pending_amounts()
        for partner in self:
            balance = balances.get(partner.id, 0.0)
            partner.hanout_credit_balance = balance
            partner.hanout_credit_pending = pending.get(partner.id, 0.0)
            if partner.hanout_credit_limit:
                partner.hanout_credit_available = (
                    partner.hanout_credit_limit
                    - balance
                    - partner.hanout_credit_pending
                )
            else:
                partner.hanout_credit_available = 0.0

    def _hanout_credit_balances(self):
        """Solde comptable du carnet de chaque client, en une passe."""
        partners = self.browse(self.ids).exists()
        balances = dict.fromkeys(partners.ids, 0.0)
        if not balances:
            return balances
        groups = self.env['account.move.line']._read_group(
            domain=[
                ('partner_id', 'in', partners.ids),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('parent_state', '=', 'posted'),
                ('reconciled', '=', False),
            ],
            groupby=['partner_id'],
            aggregates=['amount_residual:sum'],
        )
        for partner, residual in groups:
            balances[partner.id] += residual
        return balances

    def _hanout_credit_pending_amounts(self):
        """Crédit accordé dans des sessions de caisse encore ouvertes."""
        partners = self.browse(self.ids).exists()
        pending = dict.fromkeys(partners.ids, 0.0)
        if not pending:
            return pending
        # Le type « pay_later » est calculé : on le traduit par l'absence de
        # journal, seule condition SQL possible (le type n'est pas stocké).
        payments = self.env['pos.payment'].search([
            ('pos_order_id.partner_id', 'in', partners.ids),
            ('payment_method_id.journal_id', '=', False),
            ('session_id.state', 'in', ('opening_control', 'opened')),
        ])
        for payment in payments:
            pending[payment.pos_order_id.partner_id.id] += payment.amount
        return pending

    def _search_hanout_credit_balance(self, operator, value):
        """Rechercher les clients par solde de carnet (écran des débiteurs)."""
        if operator not in OPERATORS:
            raise UserError(_("Opérateur de recherche non pris en charge."))
        compare = OPERATORS[operator]
        balances = self.search([])._hanout_credit_balances()
        ids = [
            partner_id for partner_id, balance in balances.items()
            if compare(balance, value)
        ]
        return [('id', 'in', ids)]

    def action_hanout_register_credit_payment(self):
        """Ouvrir le règlement du carnet pour ce client."""
        self.ensure_one()
        wizard = self.env['hanout.credit.payment'].create({
            'partner_id': self.id,
            'amount': max(self.hanout_credit_balance, 0.0),
            'company_id': (self.company_id or self.env.company).id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Règlement du carnet — %s", self.display_name),
            'res_model': 'hanout.credit.payment',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
