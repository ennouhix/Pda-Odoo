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

OPERATION_LABELS = {
    'receipt': "Réception",
    'issue': "Sortie",
    'transfer': "Transfert",
    'inventory': "Inventaire",
}


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

    @api.model
    def receive_product(
        self, barcode: str | None, quantity, location_dest_id,
    ) -> dict:
        """Enregistrer une réception de produit vers un emplacement interne.

        :param barcode: code-barres du produit reçu.
        :param quantity: quantité reçue (nombre strictement positif).
        :param location_dest_id: identifiant de l'emplacement interne cible.
        :return: résultat JSON avec l'état de stock mis à jour.
        :raises PdaError: si l'accès, le produit, la quantité ou l'emplacement
            sont invalides, ou en cas d'erreur de validation.
        """
        def handler(product):
            qty = self._parse_quantity(quantity)
            destination = self._get_internal_location(location_dest_id)
            self._create_and_validate_move(
                product, qty, 'incoming', location_dest=destination,
            )
            return self._build_product_payload(product), {
                'quantity': qty,
                'location_dest_id': destination.id,
            }

        return self._perform_operation('receipt', barcode, handler)

    @api.model
    def issue_product(
        self, barcode: str | None, quantity, location_id,
    ) -> dict:
        """Enregistrer une sortie de stock depuis un emplacement interne.

        :param barcode: code-barres du produit sorti.
        :param quantity: quantité sortie (nombre strictement positif).
        :param location_id: identifiant de l'emplacement interne source.
        :return: résultat JSON avec l'état de stock mis à jour.
        :raises PdaError: si l'accès, le produit, la quantité, l'emplacement
            ou le stock disponible sont invalides.
        """
        def handler(product):
            qty = self._parse_quantity(quantity)
            source = self._get_internal_location(location_id)
            self._check_available_quantity(product, source, qty)
            self._create_and_validate_move(
                product, qty, 'outgoing', location=source,
            )
            return self._build_product_payload(product), {
                'quantity': qty,
                'location_id': source.id,
            }

        return self._perform_operation('issue', barcode, handler)

    @api.model
    def transfer_product(
        self, barcode: str | None, quantity, location_id, location_dest_id,
    ) -> dict:
        """Transférer un produit entre deux emplacements internes.

        :param barcode: code-barres du produit transféré.
        :param quantity: quantité transférée (nombre strictement positif).
        :param location_id: identifiant de l'emplacement interne source.
        :param location_dest_id: identifiant de l'emplacement interne cible.
        :return: résultat JSON avec l'état de stock mis à jour.
        :raises PdaError: si les emplacements sont identiques, si le stock est
            insuffisant ou en cas d'erreur de validation.
        """
        def handler(product):
            qty = self._parse_quantity(quantity)
            source = self._get_internal_location(location_id)
            destination = self._get_internal_location(location_dest_id)
            if source == destination:
                raise PdaError(
                    'invalid_location',
                    _("L'emplacement de destination doit être différent "
                      "de l'emplacement source."),
                )
            self._check_available_quantity(product, source, qty)
            self._create_and_validate_move(
                product, qty, 'internal',
                location=source, location_dest=destination,
            )
            return self._build_product_payload(product), {
                'quantity': qty,
                'location_id': source.id,
                'location_dest_id': destination.id,
            }

        return self._perform_operation('transfer', barcode, handler)

    @api.model
    def inventory_product(
        self, barcode: str | None, quantity, location_id,
    ) -> dict:
        """Fixer la quantité comptée d'un produit dans un emplacement.

        :param barcode: code-barres du produit inventorié.
        :param quantity: quantité physique comptée (nombre positif ou nul).
        :param location_id: identifiant de l'emplacement interne compté.
        :return: résultat JSON avec l'état de stock mis à jour.
        :raises PdaError: si l'accès, le produit, la quantité ou l'emplacement
            sont invalides, ou en cas de conflit d'inventaire.
        """
        def handler(product):
            qty = self._parse_quantity(quantity, allow_zero=True)
            location = self._get_internal_location(location_id)
            self._apply_inventory(product, location, qty)
            return self._build_product_payload(product), {
                'quantity': qty,
                'location_id': location.id,
            }

        return self._perform_operation('inventory', barcode, handler)

    # ------------------------------------------------------------------
    # Méthodes internes
    # ------------------------------------------------------------------
    @api.model
    def _perform_operation(self, operation: str, barcode: str | None, handler) -> dict:
        """Exécuter une opération de stock et journaliser le résultat.

        Centralise la vérification d'accès, la recherche du produit, la
        journalisation et la traduction des erreurs. ``handler`` reçoit le
        produit trouvé et retourne ``(payload, valeurs_de_journalisation)``.

        :param operation: code de l'opération (``receipt``, ``issue``...).
        :param barcode: code-barres scanné.
        :param handler: callable appliquant l'opération au produit.
        :return: résultat JSON en cas de succès.
        :raises PdaError: pour toute erreur métier ou technique.
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
            if product.tracking != 'none':
                raise PdaError(
                    'unsupported_tracking',
                    _("Les produits suivis par lot ou numéro de série ne sont "
                      "pas encore pris en charge par le PDA."),
                )
            payload, log_values = handler(product)
        except PdaError as error:
            self._log_operation(
                operation=operation,
                state='error',
                barcode=barcode,
                message=error.message,
            )
            raise
        except AccessError as error:
            _logger.warning(
                "Accès refusé lors de l'opération PDA %s : %s", operation, error,
            )
            pda_error = PdaError(
                'access_denied',
                _("Droits insuffisants pour effectuer cette opération de stock."),
            )
            self._log_operation(
                operation=operation,
                state='error',
                barcode=barcode,
                message=pda_error.message,
            )
            raise pda_error from error
        except Exception as error:  # noqa: BLE001 - barrière anti-fuite
            _logger.exception(
                "Erreur inattendue lors de l'opération PDA %s du code-barres %s",
                operation,
                barcode,
            )
            self._log_operation(
                operation=operation,
                state='error',
                barcode=barcode,
                message=str(error),
            )
            raise PdaError(
                'internal_error',
                _("Une erreur interne est survenue, veuillez réessayer."),
            ) from error

        message = _(
            "%(label)s : %(quantity)s × %(product)s",
            label=_(OPERATION_LABELS[operation]),
            quantity=log_values['quantity'],
            product=product.display_name,
        )
        self._log_operation(
            operation=operation,
            state='success',
            barcode=barcode,
            product_id=product.id,
            location_id=log_values.get('location_id', False),
            location_dest_id=log_values.get('location_dest_id', False),
            quantity=log_values['quantity'],
            message=message,
        )
        return {
            'success': True,
            'operation': operation,
            'message': message,
            **payload,
        }

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
    def _parse_quantity(self, quantity, allow_zero: bool = False) -> float:
        """Valider et convertir une quantité reçue du client PDA.

        :param quantity: valeur brute (nombre JSON, chaîne ou ``None``).
        :param allow_zero: autoriser une quantité nulle (inventaire).
        :return: quantité sous forme de ``float``.
        :raises PdaError: si la valeur n'est pas un nombre fini, ou si elle est
            nulle (hors inventaire) ou négative.
        """
        try:
            parsed = float(quantity)
        except (TypeError, ValueError):
            raise PdaError(
                'invalid_quantity',
                _("La quantité doit être un nombre."),
            ) from None
        if parsed != parsed or parsed in (float('inf'), float('-inf')):
            raise PdaError(
                'invalid_quantity',
                _("La quantité doit être un nombre fini."),
            )
        if parsed < 0 or (parsed == 0 and not allow_zero):
            raise PdaError(
                'invalid_quantity',
                _("La quantité doit être strictement positive.")
                if not allow_zero
                else _("La quantité ne peut pas être négative."),
            )
        return parsed

    @api.model
    def _get_internal_location(self, location_id):
        """Retourner un emplacement interne à partir de son identifiant.

        :param location_id: identifiant brut reçu du client PDA.
        :return: enregistrement ``stock.location`` interne.
        :raises PdaError: si l'identifiant est invalide, si l'emplacement
            n'existe pas, n'est pas interne ou appartient à une autre société.
        """
        try:
            location_id = int(location_id)
        except (TypeError, ValueError):
            raise PdaError(
                'invalid_location',
                _("L'emplacement est obligatoire."),
            ) from None
        location = self.env['stock.location'].browse(location_id).exists()
        if not location or location.usage != 'internal':
            raise PdaError(
                'invalid_location',
                _("L'emplacement sélectionné n'est pas un emplacement "
                  "interne valide."),
            )
        if location.company_id and location.company_id != self.env.company:
            raise PdaError(
                'invalid_location',
                _("L'emplacement n'appartient pas à la société courante."),
            )
        return location

    @api.model
    def _get_picking_type(self, code: str, location):
        """Trouver le type d'opération correspondant à un code donnée.

        :param code: ``incoming``, ``outgoing`` ou ``internal``.
        :param location: emplacement interne servant à déterminer l'entrepôt.
        :return: enregistrement ``stock.picking.type``.
        :raises PdaError: si aucun type d'opération n'est configuré.
        """
        warehouse = location.warehouse_id
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.env.company.id)], limit=1,
            )
        picking_type = self.env['stock.picking.type']
        if code == 'internal' and warehouse.int_type_id:
            # Type « transfert interne » de l'entrepôt, même archivé : Odoo ne
            # le crée actif que pour les réceptions/délivrances en plusieurs
            # étapes, mais il reste utilisable pour les mouvements du PDA.
            picking_type = warehouse.int_type_id
        else:
            domain = [('code', '=', code), ('warehouse_id', '=', warehouse.id)]
            picking_type = picking_type.search(domain, limit=1)
            if not picking_type:
                picking_type = picking_type.with_context(
                    active_test=False,
                ).search(domain, limit=1)
        if not picking_type:
            raise PdaError(
                'configuration_error',
                _("Aucun type d'opération de stock n'est configuré pour cet "
                  "entrepôt."),
            )
        return picking_type

    @api.model
    def _create_and_validate_move(
        self,
        product,
        quantity: float,
        code: str,
        location=None,
        location_dest=None,
    ):
        """Créer et valider un transfert d'une ligne pour un produit.

        Le transfert est validé sans assistant : la quantité réalisée est fixée
        à la demande et la ligne est marquée comme prélevée, ce qui évite les
        assistants de transfert immédiat et de reliquat.

        :param product: produit transféré.
        :param quantity: quantité réalisée.
        :param code: type d'opération (``incoming``, ``outgoing``, ``internal``).
        :param location: emplacement source (défaut du type d'opération sinon).
        :param location_dest: emplacement destination (défaut du type sinon).
        :return: le ``stock.picking`` validé.
        :raises PdaError: si la validation échoue ou reste incomplète.
        """
        picking_type = self._get_picking_type(code, location or location_dest)
        source = location or picking_type.default_location_src_id
        destination = location_dest or picking_type.default_location_dest_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'origin': 'PDA',
        })
        self.env['stock.move'].create({
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
        })
        picking.action_confirm()
        picking.move_ids.quantity = quantity
        picking.move_ids.picked = True
        picking.with_context(
            skip_backorder=True, skip_sanity_check=True,
        ).button_validate()
        if picking.state != 'done':
            raise PdaError(
                'validation_failed',
                _("Le transfert n'a pas pu être validé."),
            )
        return picking

    @api.model
    def _check_available_quantity(self, product, location, quantity: float) -> None:
        """Vérifier que le stock disponible couvre la quantité demandée.

        :param product: produit concerné.
        :param location: emplacement interne source.
        :param quantity: quantité demandée.
        :raises PdaError: si le stock disponible est insuffisant.
        """
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ])
        available = sum(quants.mapped('available_quantity'))
        if product.uom_id.compare(available, quantity) < 0:
            raise PdaError(
                'insufficient_stock',
                _("Stock insuffisant à %(location)s : %(available)s "
                  "disponible(s), %(requested)s demandé(s).",
                  location=location.complete_name,
                  available=product.uom_id.round(available),
                  requested=product.uom_id.round(quantity)),
            )

    @api.model
    def _apply_inventory(self, product, location, quantity: float) -> None:
        """Appliquer une quantité inventoriée à un produit dans un emplacement.

        :param product: produit inventorié.
        :param location: emplacement interne compté.
        :param quantity: quantité physique comptée.
        :raises PdaError: si l'ajustement est bloqué par un conflit d'inventaire.
        """
        quant_model = self.env['stock.quant'].with_context(inventory_mode=True)
        quant = quant_model.search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ], limit=1)
        if quant:
            quant.inventory_quantity = quantity
        else:
            quant = quant_model.create({
                'product_id': product.id,
                'location_id': location.id,
                'inventory_quantity': quantity,
            })
        result = quant.action_apply_inventory()
        if isinstance(result, dict):
            raise PdaError(
                'inventory_conflict',
                _("Un conflit d'inventaire empêche la mise à jour, veuillez "
                  "rafraîchir puis réessayer."),
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
