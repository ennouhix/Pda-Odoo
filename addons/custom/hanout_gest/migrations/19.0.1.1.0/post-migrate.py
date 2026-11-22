# -*- coding: utf-8 -*-
"""Migration 19.0.1.1.0 : numérotation des tickets par magasin.

Chaque magasin hanout reçoit une séquence de ticket unique
(``HCS/2026/000042``) et les caisses existantes sont rattachées à cette
séquence à la place de celle qu'Odoo avait créée par caisse.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    shops = env['hanout.shop'].search([])
    shops._ensure_ticket_sequence()
    configs = env['pos.config'].search([('hanout_shop_id', '!=', False)])
    configs._hanout_use_shop_sequence()
    _logger.info(
        "Hanout : %s magasin(s) et %s caisse(s) numérotent désormais leurs "
        "tickets par magasin.", len(shops), len(configs),
    )
