# -*- coding: utf-8 -*-
"""Migration 19.0.1.1.1 : magasin des caisses hanout.

Le magasin n'est plus une contrainte de base sur ``pos.config`` (une base
peut contenir des caisses Point de Vente antérieures au module) mais une
règle métier : toute caisse en mode hanout simplifié doit avoir un magasin.

Cette migration remet le mode simplifié à zéro sur les caisses sans magasin,
héritées du mode par défaut du champ, et retire la contrainte NOT NULL que
l'installation précédente avait pu poser sur certaines bases.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        "ALTER TABLE pos_config ALTER COLUMN hanout_shop_id DROP NOT NULL"
    )
    stray_configs = env['pos.config'].search([
        ('hanout_shop_id', '=', False),
        ('hanout_simple_mode', '=', True),
    ])
    if stray_configs:
        stray_configs.write({'hanout_simple_mode': False})
        _logger.info(
            "Hanout : mode simplifié désactivé sur %s caisse(s) sans magasin.",
            len(stray_configs),
        )
