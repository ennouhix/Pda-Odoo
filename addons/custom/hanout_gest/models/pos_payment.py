# -*- coding: utf-8 -*-
"""Contrôle du plafond du carnet à l'encaissement."""
from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class PosPayment(models.Model):
    """Refuser une vente à crédit qui dépasse le plafond du client."""

    _inherit = 'pos.payment'

    @api.model_create_multi
    def create(self, vals_list):
        # Contrôle avant écriture : un paiement refusé ne laisse rien en base.
        for values in vals_list:
            self._hanout_check_credit_limit(values)
        return super().create(vals_list)

    def _hanout_check_credit_limit(self, values):
        """Vérifier le plafond du carnet avant d'enregistrer un paiement.

        Le solde du carnet est complété par le crédit accordé dans les
        sessions encore ouvertes, et par le paiement en cours : c'est le
        solde qu'aurait le client après cette vente qui est comparé au
        plafond.
        """
        method = self.env['pos.payment.method'].browse(
            values.get('payment_method_id')
        ).exists()
        amount = values.get('amount') or 0.0
        if not method or method.type != 'pay_later' or amount <= 0:
            # Un retour au client vient réduire le carnet.
            return
        order = self.env['pos.order'].browse(values.get('pos_order_id'))
        partner = order.partner_id
        if not partner:
            raise UserError(_(
                "Une vente à crédit (carnet) nécessite un client : "
                "choisissez le client sur le ticket %(order)s.",
                order=order.pos_reference or order.name or '',
            ))
        limit = partner.hanout_credit_limit
        if not limit:
            return
        # Le solde est calculé à la lecture : on le rafraîchit pour tenir
        # compte des ventes déjà enregistrées dans la transaction.
        partner.invalidate_recordset()
        committed = partner.hanout_credit_balance + partner.hanout_credit_pending
        rounding = partner.hanout_currency_id.rounding
        if float_compare(committed + amount, limit, precision_rounding=rounding) > 0:
            raise UserError(_(
                "Plafond du carnet dépassé pour %(partner)s : le solde "
                "atteindrait %(balance)s pour un plafond de %(limit)s.\n"
                "Encaissez une partie en espèces ou réglez le carnet avant "
                "de continuer.",
                partner=partner.display_name,
                balance=committed + amount,
                limit=limit,
            ))
