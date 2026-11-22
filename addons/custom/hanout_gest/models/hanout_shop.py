# -*- coding: utf-8 -*-
"""Magasin hanout : point de rattachement des caisses et des dépenses."""
from odoo import api, _, fields, models
from odoo.exceptions import UserError, ValidationError


class HanoutShop(models.Model):
    """Boutique de proximité gérée dans Odoo.

    Le magasin relie un entrepôt (pour le stock), une ou plusieurs caisses
    Point de Vente et les dépenses de caisse du jour.
    """

    _name = 'hanout.shop'
    _description = "Magasin hanout"
    _order = 'name, id'

    _unique_code_company = models.Constraint(
        'unique(code, company_id)',
        "Le code du magasin doit être unique par société.",
    )

    name = fields.Char(
        string="Nom du magasin",
        required=True,
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Code court du magasin, par exemple « H1 » ou « CENTRE ».",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        string="Devise",
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string="Entrepôt",
        domain="[('company_id', '=', company_id)]",
        ondelete='restrict',
        help="Entrepôt dont le stock alimente ce magasin.",
    )
    pos_config_ids = fields.One2many(
        comodel_name='pos.config',
        inverse_name='hanout_shop_id',
        string="Caisses",
        help="Caisses Point de Vente rattachées à ce magasin.",
    )
    phone = fields.Char(
        string="Téléphone",
        help="Numéro affiché sur le ticket de caisse du magasin.",
    )
    address = fields.Char(
        string="Adresse",
        help="Adresse courte affichée sur le ticket de caisse.",
    )
    sequence_id = fields.Many2one(
        comodel_name='ir.sequence',
        string="Séquence de ticket",
        copy=False,
        readonly=True,
        help="Numérotation des tickets des caisses du magasin : le code du "
             "magasin, l'année puis un compteur, par exemple « HCS/2026/000042 ».",
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
    )
    note = fields.Text(
        string="Notes",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Créer la séquence de ticket à la création du magasin."""
        shops = super().create(vals_list)
        shops._ensure_ticket_sequence()
        return shops

    def write(self, values):
        """Aligner le préfixe de la séquence sur le code du magasin."""
        result = super().write(values)
        if 'code' in values:
            for shop in self.filtered('sequence_id'):
                shop.sequence_id.sudo().prefix = shop._ticket_sequence_prefix()
        return result

    def _ticket_sequence_prefix(self):
        """Préfixe de numérotation des tickets du magasin."""
        self.ensure_one()
        return f"{self.code or 'HT'}/%(range_year)s/"

    def _ensure_ticket_sequence(self):
        """Créer la séquence de ticket des magasins qui n'en ont pas.

        Appelée à la création du magasin et par la migration du module, pour
        que chaque magasin existant possède sa numérotation propre.
        """
        for shop in self:
            if shop.sequence_id:
                continue
            shop.sequence_id = self.env['ir.sequence'].sudo().create({
                'name': _("Ticket %s", shop.display_name),
                'code': 'hanout.shop.ticket',
                'prefix': shop._ticket_sequence_prefix(),
                'padding': 6,
                'company_id': shop.company_id.id,
            })

    def action_hanout_open_pos(self):
        """Démarrer la caisse du magasin depuis la fiche magasin.

        Ouvre directement l'interface de vente quand le magasin n'a qu'une
        caisse ; sinon propose le choix parmi ses caisses, chacune disposant
        du bouton « Ouvrir la caisse » du tableau de bord Point de Vente.
        """
        self.ensure_one()
        configs = self.pos_config_ids.filtered('active')
        if not configs:
            raise UserError(_(
                "Aucune caisse n'est rattachée au magasin %(shop)s : "
                "ajoutez une caisse Point de Vente dans le champ « Caisses ».",
                shop=self.display_name,
            ))
        if len(configs) > 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _("Caisses — %s", self.display_name),
                'res_model': 'pos.config',
                'view_mode': 'kanban,list,form',
                'domain': [('id', 'in', configs.ids)],
                'target': 'current',
            }
        return configs.open_ui()

    @api.constrains('warehouse_id', 'company_id')
    def _check_warehouse_company(self):
        """Vérifier que l'entrepôt appartient à la société du magasin."""
        for shop in self:
            if (
                shop.warehouse_id
                and shop.warehouse_id.company_id != shop.company_id
            ):
                raise ValidationError(
                    "L'entrepôt sélectionné n'appartient pas à la société "
                    "du magasin."
                )
