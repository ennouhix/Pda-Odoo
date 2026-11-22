# -*- coding: utf-8 -*-
"""Rattachement d'une caisse Point de Vente à un magasin hanout."""
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PosConfig(models.Model):
    """Ajoute le magasin hanout et le mode caisse simplifié."""

    _inherit = 'pos.config'

    hanout_shop_id = fields.Many2one(
        comodel_name='hanout.shop',
        string="Magasin hanout",
        domain="[('company_id', '=', company_id)]",
        ondelete='restrict',
        index=True,
        help="Magasin dont cette caisse dépend : les dépenses, la clôture "
             "journalière et la numérotation des tickets y sont rattachées. "
             "Obligatoire pour toute caisse en mode hanout simplifié.",
    )
    hanout_shop_name = fields.Char(
        string="Nom du magasin",
        related='hanout_shop_id.name',
        readonly=True,
    )
    hanout_shop_address = fields.Char(
        string="Adresse du magasin",
        related='hanout_shop_id.address',
        readonly=True,
    )
    hanout_shop_phone = fields.Char(
        string="Téléphone du magasin",
        related='hanout_shop_id.phone',
        readonly=True,
    )
    hanout_simple_mode = fields.Boolean(
        string="Mode hanout simplifié",
        default=False,
        help="Interface de caisse épurée pour le caissier : grandes touches "
             "produits, pas de pavé quantité/prix/remise, pas de boutons "
             "client, note ni remboursement. Le bouton d'encaissement et le "
             "paiement rapide restent disponibles.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Activer le mode simplifié sur toute caisse rattachée à un magasin."""
        for values in vals_list:
            if values.get('hanout_shop_id') and 'hanout_simple_mode' not in values:
                values['hanout_simple_mode'] = True
        return super().create(vals_list)

    @api.constrains('hanout_shop_id', 'hanout_simple_mode')
    def _check_hanout_shop_required(self):
        """Une caisse en mode hanout doit avoir un magasin.

        Le champ reste facultatif en base : une base peut déjà contenir des
        caisses Point de Vente qui ne sont pas des caisses hanout (créées
        avant l'installation du module).
        """
        for config in self:
            if config.hanout_simple_mode and not config.hanout_shop_id:
                raise ValidationError(_(
                    "La caisse %(config)s est en mode hanout simplifié : "
                    "renseignez son magasin hanout.",
                    config=config.display_name,
                ))

    def _create_sequences(self):
        """Numéroter les tickets avec la séquence du magasin hanout.

        Odoo crée une séquence de ticket par caisse. Dans un hanout, toutes
        les caisses d'un même magasin partagent une numérotation unique : le
        ticket indique ainsi le magasin et non la caisse.
        """
        super()._create_sequences()
        self._hanout_use_shop_sequence()

    def write(self, values):
        """Suivre le changement de magasin sur la numérotation des tickets."""
        result = super().write(values)
        if 'hanout_shop_id' in values:
            self._hanout_use_shop_sequence()
        return result

    def _hanout_use_shop_sequence(self):
        """Rattacher la séquence de ticket de la caisse à celle du magasin."""
        for config in self:
            sequence = config.hanout_shop_id.sequence_id
            if not sequence or config.order_seq_id == sequence:
                continue
            # La séquence créée par Odoo n'a jamais servi pour une caisse
            # neuve : on la désactive plutôt que de laisser une séquence
            # orpheline dans la liste des séquences.
            old_sequence = config.order_seq_id
            if old_sequence and old_sequence.number_next_actual == 1:
                old_sequence.sudo().active = False
            config.order_seq_id = sequence

    @api.constrains('hanout_shop_id', 'company_id')
    def _check_hanout_shop_company(self):
        """La caisse et son magasin hanout doivent être dans la même société."""
        for config in self:
            if (
                config.hanout_shop_id
                and config.hanout_shop_id.company_id != config.company_id
            ):
                raise ValidationError(_(
                    "La caisse %(config)s et le magasin %(shop)s "
                    "n'appartiennent pas à la même société.",
                    config=config.display_name,
                    shop=config.hanout_shop_id.display_name,
                ))

    def _hanout_ensure_credit_method(self):
        """Retourner le moyen de paiement « Crédit carnet » de la société.

        Créé au besoin sur le type natif ``pay_later`` : aucun journal, donc
        aucune écriture de trésorerie, et « Identify Customer » coché pour que
        la créance soit portée au compte du client et non à un compte
        d'attente anonyme.
        """
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('journal_id', '=', False),
            ('split_transactions', '=', True),
        ]
        method = self.env['pos.payment.method'].search(
            domain + [('name', '=', _("Crédit carnet"))], limit=1
        )
        if not method:
            # Une base issue des données de démonstration Point de Vente
            # possède déjà le moyen de paiement natif « Customer Account » :
            # inutile d'en créer un second.
            method = self.env['pos.payment.method'].search(domain, limit=1)
        if not method:
            method = self.env['pos.payment.method'].create({
                'name': _("Crédit carnet"),
                'company_id': self.company_id.id,
                'split_transactions': True,
                'sequence': 20,
            })
        return method

    def action_hanout_apply_simple_mode(self):
        """Régler la caisse pour un usage hanout par un caissier débutant.

        L'interface simplifiée est activée, les options avancées (remises,
        listes de prix, pourboires, mode restaurant) sont coupées et le
        paiement rapide est branché sur l'espèce pour encaisser en un clic.
        """
        for config in self:
            if config.current_session_id:
                raise UserError(_(
                    "Fermez la caisse %(config)s avant d'appliquer le mode "
                    "hanout : les moyens de paiement ne sont pas modifiables "
                    "pendant une session.",
                    config=config.display_name,
                ))
            cash_methods = config.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count
            )[:1]
            if not cash_methods:
                raise UserError(_(
                    "Ajoutez d'abord un moyen de paiement en espèces à la "
                    "caisse %(config)s : le mode hanout encaisse en un clic.",
                    config=config.display_name,
                ))
            credit_method = config._hanout_ensure_credit_method()
            commands = [Command.clear(), Command.link(cash_methods.id)]
            config.write({
                'payment_method_ids': [Command.link(credit_method.id)],
                'hanout_simple_mode': True,
                'manual_discount': False,
                'iface_tipproduct': False,
                'use_pricelist': False,
                'module_pos_restaurant': False,
                'iface_big_scrollbars': True,
                'show_product_images': True,
                'use_fast_payment': bool(cash_methods),
                'fast_payment_method_ids': commands,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Mode hanout activé"),
                'message': _(
                    "La caisse utilise l'interface simplifiée et le paiement "
                    "rapide en espèces."
                ),
                'type': 'success',
                'sticky': False,
            },
        }
