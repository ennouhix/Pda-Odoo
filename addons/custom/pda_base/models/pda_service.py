# -*- coding: utf-8 -*-
"""Service métier de l'application PDA.

Toute la logique métier exposée par les endpoints JSON vit ici, dans un
modèle abstrait : les contrôleurs restent fins et ne font que traduire les
appels HTTP en appels de méthodes.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

PDA_USER_GROUP = 'pda_base.group_pda_user'


class PdaError(Exception):
    """Erreur métier destinée à être renvoyée au client PDA.

    Le message porté par cette exception est sûr : il ne contient jamais de
    trace Python et peut être exposé tel quel dans la réponse JSON.
    """

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def as_dict(self) -> dict:
        """Retourner la représentation JSON structurée de l'erreur."""
        return {
            'success': False,
            'error_code': self.error_code,
            'message': self.message,
        }


class PdaService(models.AbstractModel):
    """Point d'entrée métier des opérations PDA."""

    _name = 'pda.service'
    _description = "Service métier de l'application PDA"

    # ------------------------------------------------------------------
    # API publiques
    # ------------------------------------------------------------------
    @api.model
    def lookup_product_by_barcode(self, barcode: str | None) -> dict:
        """Rechercher un produit par code-barres et retourner son stock.

        :param barcode: code-barres scanné (chaîne, peut être vide).
        :return: dictionnaire ``{'success': True, ...}`` décrivant le produit
            et le détail de ses quantités par emplacement interne.
        :raises PdaError: si l'accès est refusé, le code-barres invalide ou
            inconnu, ou en cas d'erreur interne.
        """
        barcode = (barcode or '').strip()
        try:
            self._check_pda_access()
            if not barcode:
                raise PdaError(
                    'invalid_barcode',
                    _("Le code-barres est obligatoire."),
                )
            product = self.env['product.product'].search(
                [('barcode', '=', barcode)], limit=1,
            )
            if not product:
                raise PdaError(
                    'unknown_barcode',
                    _("Aucun produit ne correspond au code-barres %(barcode)s.",
                      barcode=barcode),
                )
            payload = self._build_product_payload(product)
        except PdaError as error:
            self._log_operation(
                operation='lookup',
                state='error',
                barcode=barcode,
                message=error.message,
            )
            raise
        except AccessError as error:
            _logger.warning("Accès refusé lors du lookup PDA : %s", error)
            pda_error = PdaError(
                'access_denied',
                _("Droits insuffisants pour consulter les données de stock."),
            )
            self._log_operation(
                operation='lookup',
                state='error',
                barcode=barcode,
                message=pda_error.message,
            )
            raise pda_error from error
        except Exception as error:  # noqa: BLE001 - barrière anti-fuite
            _logger.exception(
                "Erreur inattendue lors du lookup PDA du code-barres %s",
                barcode,
            )
            self._log_operation(
                operation='lookup',
                state='error',
                barcode=barcode,
                message=str(error),
            )
            raise PdaError(
                'internal_error',
                _("Une erreur interne est survenue, veuillez réessayer."),
            ) from error

        self._log_operation(
            operation='lookup',
            state='success',
            barcode=barcode,
            product_id=product.id,
            message=_("Produit %(name)s consulté.", name=product.name),
        )
        return {'success': True, **payload}

    @api.model
    def get_internal_locations(self) -> dict:
        """Lister les emplacements de stock internes.

        :return: dictionnaire ``{'success': True, 'locations': [...]}`` où
            chaque emplacement expose son identifiant, son nom complet et son
            code-barres.
        :raises PdaError: si l'accès est refusé ou en cas d'erreur interne.
        """
        try:
            self._check_pda_access()
            locations = self.env['stock.location'].search(
                [('usage', '=', 'internal')],
                order='complete_name, id',
            )
            payload = [
                {
                    'id': location.id,
                    'name': location.complete_name,
                    'barcode': location.barcode or '',
                }
                for location in locations
            ]
        except PdaError as error:
            self._log_operation(
                operation='lookup',
                state='error',
                message=error.message,
            )
            raise
        except AccessError as error:
            _logger.warning("Accès refusé lors du listage PDA : %s", error)
            pda_error = PdaError(
                'access_denied',
                _("Droits insuffisants pour consulter les emplacements."),
            )
            self._log_operation(
                operation='lookup',
                state='error',
                message=pda_error.message,
            )
            raise pda_error from error
        except Exception as error:  # noqa: BLE001 - barrière anti-fuite
            _logger.exception("Erreur inattendue lors du listage des emplacements PDA")
            self._log_operation(
                operation='lookup',
                state='error',
                message=str(error),
            )
            raise PdaError(
                'internal_error',
                _("Une erreur interne est survenue, veuillez réessayer."),
            ) from error

        self._log_operation(
            operation='lookup',
            state='success',
            message=_("%(count)s emplacement(s) interne(s) listé(s).",
                      count=len(payload)),
        )
        return {'success': True, 'locations': payload}

    # ------------------------------------------------------------------
    # Méthodes internes
    # ------------------------------------------------------------------
    @api.model
    def _check_pda_access(self) -> None:
        """Vérifier que l'utilisateur courant appartient au groupe PDA.

        :raises PdaError: si l'utilisateur n'a pas le groupe ``group_pda_user``.
        """
        if not self.env.user.has_group(PDA_USER_GROUP):
            raise PdaError(
                'access_denied',
                _("Vous n'avez pas accès à l'application PDA."),
            )

    @api.model
    def _build_product_payload(self, product) -> dict:
        """Construire la représentation JSON d'un produit et de son stock.

        Seuls les emplacements internes sont pris en compte. Aucun ``sudo()``
        n'est utilisé : les droits de l'utilisateur courant s'appliquent.

        :param product: enregistrement ``product.product``.
        :return: dictionnaire décrivant le produit et ses quantités.
        """
        quants = self.env['stock.quant'].search(
            [
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
            ],
            order='location_id, id',
        )
        uom = product.uom_id
        locations = []
        total_quantity = 0.0
        total_available_quantity = 0.0
        for quant in quants:
            total_quantity += quant.quantity
            total_available_quantity += quant.available_quantity
            locations.append({
                'location_id': quant.location_id.id,
                'location_name': quant.location_id.complete_name,
                'quantity': uom.round(quant.quantity),
                'available_quantity': uom.round(quant.available_quantity),
            })
        return {
            'id': product.id,
            'reference': product.default_code or '',
            'name': product.name,
            'barcode': product.barcode or '',
            'uom': uom.name,
            'total_quantity': uom.round(total_quantity),
            'total_available_quantity': uom.round(total_available_quantity),
            'locations': locations,
        }

    @api.model
    def _log_operation(
        self,
        operation: str,
        state: str,
        message: str = '',
        barcode: str = '',
        product_id: int = False,
        location_id: int = False,
        location_dest_id: int = False,
        quantity: float = 0.0,
    ) -> None:
        """Écrire une ligne dans le journal PDA.

        Le journal est écrit en ``sudo()`` : c'est la seule opération pour
        laquelle les droits sont contournés, conformément au cahier des
        charges. L'utilisateur d'origine est toujours conservé dans
        ``user_id``. Une erreur d'écriture du journal ne doit jamais faire
        échouer l'opération métier.
        """
        try:
            self.env['pda.log'].sudo().create({
                'user_id': self.env.uid,
                'operation': operation,
                'state': state,
                'message': message,
                'barcode': barcode,
                'product_id': product_id or False,
                'location_id': location_id or False,
                'location_dest_id': location_dest_id or False,
                'quantity': quantity,
            })
        except Exception:  # noqa: BLE001 - le journal ne doit pas bloquer
            _logger.exception("Impossible d'écrire dans le journal PDA")
