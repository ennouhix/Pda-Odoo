# -*- coding: utf-8 -*-
"""Enrichissement de la session POS pour la clôture hanout."""
from odoo import api, fields, models


class PosSession(models.Model):
    """Session de caisse : dépenses du jour et théorique de caisse ajusté.

    Le théorique de caisse calculé par Odoo ne déduit que les mouvements
    d'espèces enregistrés. Dans un hanout, des dépenses sont payées en
    espèces sans passer par la caisse : elles sont donc soustraites ici.
    """

    _inherit = 'pos.session'

    hanout_shop_id = fields.Many2one(
        comodel_name='hanout.shop',
        related='config_id.hanout_shop_id',
        string="Magasin",
        store=True,
        index=True,
        readonly=True,
    )
    hanout_expense_ids = fields.One2many(
        comodel_name='hanout.expense',
        inverse_name='session_id',
        string="Dépenses de caisse",
    )
    hanout_expense_total = fields.Monetary(
        string="Total des dépenses",
        compute='_compute_hanout_expense_total',
        currency_field='currency_id',
    )

    @api.depends('hanout_expense_ids.amount')
    def _compute_hanout_expense_total(self):
        for session in self:
            session.hanout_expense_total = sum(
                session.hanout_expense_ids.mapped('amount')
            )

    @api.depends(
        'payment_method_ids',
        'order_ids',
        'cash_register_balance_start',
        'hanout_expense_ids.amount',
    )
    def _compute_cash_balance(self):
        """Déduire les dépenses hanout du théorique de caisse."""
        super()._compute_cash_balance()
        for session in self:
            if not session.cash_control or not session.hanout_expense_total:
                continue
            session.cash_register_balance_end -= session.hanout_expense_total
            session.cash_register_difference = (
                session.cash_register_balance_end_real
                - session.cash_register_balance_end
            )

    def action_hanout_view_expenses(self):
        """Ouvrir les dépenses de caisse de la session courante."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'hanout_gest.action_hanout_expense',
        )
        action['domain'] = [('session_id', '=', self.id)]
        action['context'] = {
            'default_session_id': self.id,
            'default_shop_id': self.hanout_shop_id.id,
        }
        return action
