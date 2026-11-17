# -*- coding: utf-8 -*-
"""Endpoints JSON-RPC de l'application PDA.

Les contrôleurs sont volontairement fins : ils valident le transport HTTP,
délèguent au modèle ``pda.service`` et traduisent les erreurs métier en JSON
structuré. Aucune trace Python n'est renvoyée au client.
"""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.pda_base.models.pda_service import PdaError

_logger = logging.getLogger(__name__)


class PdaController(http.Controller):
    """Expose les endpoints JSON utilisés par le futur client PDA."""

    @http.route(
        '/pda/api/product/by_barcode',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def product_by_barcode(self, barcode: str | None = None, **kwargs) -> dict:
        """Rechercher un produit par code-barres.

        :param barcode: code-barres scanné.
        :return: résultat JSON du service PDA.
        """
        return self._call_service('lookup_product_by_barcode', barcode)

    @http.route(
        '/pda/api/locations',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def locations(self, **kwargs) -> dict:
        """Lister les emplacements de stock internes.

        :return: résultat JSON du service PDA.
        """
        return self._call_service('get_internal_locations')

    @http.route(
        '/pda/api/receipt',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def receipt(
        self, barcode=None, quantity=None, location_dest_id=None, **kwargs,
    ) -> dict:
        """Enregistrer une réception vers un emplacement interne."""
        return self._call_service(
            'receive_product', barcode, quantity, location_dest_id,
        )

    @http.route(
        '/pda/api/issue',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def issue(self, barcode=None, quantity=None, location_id=None, **kwargs) -> dict:
        """Enregistrer une sortie de stock depuis un emplacement interne."""
        return self._call_service(
            'issue_product', barcode, quantity, location_id,
        )

    @http.route(
        '/pda/api/transfer',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def transfer(
        self,
        barcode=None,
        quantity=None,
        location_id=None,
        location_dest_id=None,
        **kwargs,
    ) -> dict:
        """Transférer un produit entre deux emplacements internes."""
        return self._call_service(
            'transfer_product', barcode, quantity, location_id, location_dest_id,
        )

    @http.route(
        '/pda/api/inventory',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def inventory(
        self, barcode=None, quantity=None, location_id=None, **kwargs,
    ) -> dict:
        """Fixer la quantité comptée d'un produit dans un emplacement."""
        return self._call_service(
            'inventory_product', barcode, quantity, location_id,
        )

    @staticmethod
    def _call_service(method_name: str, *args, **kwargs) -> dict:
        """Appeler une méthode du service PDA et sérialiser les erreurs.

        :param method_name: nom de la méthode de ``pda.service``.
        :return: dictionnaire JSON, succès ou erreur structurée.
        """
        service = request.env['pda.service']
        try:
            return getattr(service, method_name)(*args, **kwargs)
        except PdaError as error:
            return error.as_dict()
        except Exception:  # noqa: BLE001 - barrière anti-fuite
            _logger.exception(
                "Erreur inattendue sur l'endpoint PDA %s", method_name,
            )
            return {
                'success': False,
                'error_code': 'internal_error',
                'message': "Une erreur interne est survenue, veuillez réessayer.",
            }
