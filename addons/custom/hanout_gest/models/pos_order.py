# -*- coding: utf-8 -*-
"""Nom des tickets de caisse hanout."""
from odoo import models


class PosOrder(models.Model):
    """Tickets numérotés par magasin : ``HCS/2026/000042``.

    Odoo compose le nom du ticket avec le préfixe de séquence, un séparateur
    « - » puis le numéro. Pour un hanout, le préfixe contient déjà le code du
    magasin et l'année (``HCS/2026/``) : on le colle directement au numéro.
    """

    _inherit = 'pos.order'

    def _get_order_name_from_pos_reference(self, session=None):
        self.ensure_one()
        session = session or self.session_id
        prefix, suffix = session.config_id.order_seq_id._get_prefix_suffix()
        if not prefix:
            return super()._get_order_name_from_pos_reference(session)
        return f"{prefix}{self.get_reference_last_part()}{suffix}"
