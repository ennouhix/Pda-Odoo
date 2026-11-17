# -*- coding: utf-8 -*-
"""Tests du socle backend pda_base (service métier et endpoints HTTP)."""
from odoo.tests import HttpCase, TransactionCase

from odoo.addons.pda_base.models.pda_service import PdaError

TEST_BARCODE = 'PDA-TEST-001'


class PdaTestDataMixin:
    """Données de démonstration partagées par les tests service et HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pda_user_group = cls.env.ref('pda_base.group_pda_user')
        cls.stock_user_group = cls.env.ref('stock.group_stock_user')
        cls.internal_location = cls.env['stock.location'].create({
            'name': 'PDA Test Shelf',
            'usage': 'internal',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Produit PDA Test',
            'default_code': 'PDA-TEST-REF',
            'barcode': TEST_BARCODE,
            'type': 'consu',
            'is_storable': True,
        })
        cls.env['stock.quant'].create({
            'product_id': cls.product.id,
            'location_id': cls.internal_location.id,
            'quantity': 7.0,
        })
        cls.operator = cls.env['res.users'].create({
            'name': 'Opérateur PDA',
            'login': 'pda_operator',
            'password': 'pda_operator',
            # Les opérations de stock exigent aussi les droits Inventaire.
            'group_ids': [(6, 0, [
                cls.pda_user_group.id, cls.stock_user_group.id,
            ])],
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'Utilisateur hors PDA',
            'login': 'pda_outsider',
            'password': 'pda_outsider',
            'group_ids': [(6, 0, [cls.stock_user_group.id])],
        })


class TestPdaService(PdaTestDataMixin, TransactionCase):
    """Tests de la logique métier portée par ``pda.service``."""

    def _lookup_expect_error(self, user, barcode):
        """Appeler le service en attendant une ``PdaError``.

        Odoo 19 enveloppe ``assertRaises`` dans un savepoint annulé en cas
        d'exception : l'utiliser effacerait la ligne de journal créée pendant
        l'erreur, que ces tests doivent justement vérifier. On capture donc
        l'exception manuellement pour conserver la transaction.
        """
        try:
            self.env['pda.service'].with_user(user).lookup_product_by_barcode(
                barcode,
            )
        except PdaError as error:
            return error
        self.fail("Une PdaError était attendue.")

    def test_lookup_product_found(self):
        """Un code-barres connu renvoie le produit et son stock."""
        result = self.env['pda.service'].with_user(
            self.operator,
        ).lookup_product_by_barcode(TEST_BARCODE)

        self.assertTrue(result['success'])
        self.assertEqual(result['id'], self.product.id)
        self.assertEqual(result['reference'], 'PDA-TEST-REF')
        self.assertEqual(result['name'], 'Produit PDA Test')
        self.assertEqual(result['barcode'], TEST_BARCODE)
        self.assertAlmostEqual(result['total_available_quantity'], 7.0)
        self.assertEqual(len(result['locations']), 1)
        self.assertEqual(
            result['locations'][0]['location_id'],
            self.internal_location.id,
        )
        self.assertAlmostEqual(result['locations'][0]['available_quantity'], 7.0)

    def test_lookup_unknown_barcode(self):
        """Un code-barres inconnu lève une erreur métier structurée."""
        barcode = 'PDA-TEST-UNKNOWN'
        error = self._lookup_expect_error(self.operator, barcode)

        self.assertEqual(error.error_code, 'unknown_barcode')
        self.assertIn(barcode, error.message)
        log = self.env['pda.log'].search([
            ('barcode', '=', barcode),
            ('user_id', '=', self.operator.id),
        ])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'error')
        self.assertEqual(log.operation, 'lookup')

    def test_lookup_access_denied(self):
        """Un utilisateur hors groupe PDA ne peut pas appeler le service."""
        error = self._lookup_expect_error(self.outsider, TEST_BARCODE)

        self.assertEqual(error.error_code, 'access_denied')
        log = self.env['pda.log'].search([('user_id', '=', self.outsider.id)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'error')

    def test_log_created_on_success(self):
        """Un lookup réussi crée une ligne de journal pour l'opérateur."""
        self.env['pda.service'].with_user(
            self.operator,
        ).lookup_product_by_barcode(TEST_BARCODE)

        log = self.env['pda.log'].search([('user_id', '=', self.operator.id)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.operation, 'lookup')
        self.assertEqual(log.state, 'success')
        self.assertEqual(log.product_id, self.product)
        self.assertEqual(log.barcode, TEST_BARCODE)

    def test_internal_locations(self):
        """Le service liste les emplacements internes avec leur code-barres."""
        result = self.env['pda.service'].with_user(
            self.operator,
        ).get_internal_locations()

        self.assertTrue(result['success'])
        location_ids = [location['id'] for location in result['locations']]
        self.assertIn(self.internal_location.id, location_ids)
        listed = next(
            location for location in result['locations']
            if location['id'] == self.internal_location.id
        )
        self.assertEqual(listed['name'], self.internal_location.complete_name)


class TestPdaHttp(PdaTestDataMixin, HttpCase):
    """Tests des endpoints JSON-RPC exposés par le contrôleur PDA."""

    def _call_pda(self, route, params):
        """Appeler un endpoint PDA via JSON-RPC et retourner le résultat."""
        response = self.url_open(route, json={
            'jsonrpc': '2.0',
            'method': 'call',
            'id': 1,
            'params': params,
        })
        self.assertEqual(response.status_code, 200)
        return response.json()['result']

    def test_http_product_found(self):
        """L'endpoint produit renvoie les informations attendues."""
        self.authenticate('pda_operator', 'pda_operator')
        result = self._call_pda(
            '/pda/api/product/by_barcode', {'barcode': TEST_BARCODE},
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['reference'], 'PDA-TEST-REF')
        self.assertAlmostEqual(result['total_available_quantity'], 7.0)

    def test_http_unknown_barcode(self):
        """L'endpoint produit renvoie une erreur JSON sans trace Python."""
        self.authenticate('pda_operator', 'pda_operator')
        result = self._call_pda(
            '/pda/api/product/by_barcode', {'barcode': 'INCONNU-999'},
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'unknown_barcode')
        self.assertIn('message', result)
        self.assertNotIn('traceback', result)

    def test_http_access_denied(self):
        """Un utilisateur sans le groupe PDA reçoit une erreur d'accès."""
        self.authenticate('pda_outsider', 'pda_outsider')
        result = self._call_pda(
            '/pda/api/product/by_barcode', {'barcode': TEST_BARCODE},
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'access_denied')

    def test_http_locations(self):
        """L'endpoint emplacements renvoie les emplacements internes."""
        self.authenticate('pda_operator', 'pda_operator')
        result = self._call_pda('/pda/api/locations', {})

        self.assertTrue(result['success'])
        location_ids = [location['id'] for location in result['locations']]
        self.assertIn(self.internal_location.id, location_ids)

    def test_http_receipt(self):
        """L'endpoint réception valide un transfert entrant réel."""
        self.authenticate('pda_operator', 'pda_operator')
        result = self._call_pda('/pda/api/receipt', {
            'barcode': TEST_BARCODE,
            'quantity': 5,
            'location_dest_id': self.internal_location.id,
        })

        self.assertTrue(result['success'])
        self.assertEqual(result['operation'], 'receipt')
        self.assertAlmostEqual(result['total_available_quantity'], 12.0)

    def test_http_issue_insufficient_stock(self):
        """L'endpoint sortie renvoie une erreur structurée sans trace."""
        self.authenticate('pda_operator', 'pda_operator')
        result = self._call_pda('/pda/api/issue', {
            'barcode': TEST_BARCODE,
            'quantity': 999,
            'location_id': self.internal_location.id,
        })

        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'insufficient_stock')
        self.assertNotIn('traceback', result)


class TestPdaOperations(PdaTestDataMixin, TransactionCase):
    """Tests des opérations de stock exposées par ``pda.service``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.second_location = cls.env['stock.location'].create({
            'name': 'PDA Test Bin 2',
            'usage': 'internal',
        })

    def _service(self, user=None):
        """Retourner ``pda.service`` exécuté en tant qu'opérateur PDA."""
        return self.env['pda.service'].with_user(user or self.operator)

    def _expect_operation_error(self, method_name, *args):
        """Appeler une opération en attendant une ``PdaError``."""
        try:
            getattr(self._service(), method_name)(*args)
        except PdaError as error:
            return error
        self.fail("Une PdaError était attendue.")

    def test_receipt_creates_stock(self):
        """Une réception augmente le stock et valide un transfert entrant."""
        result = self._service().receive_product(
            TEST_BARCODE, 5, self.internal_location.id,
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['operation'], 'receipt')
        self.assertAlmostEqual(result['total_available_quantity'], 12.0)
        picking = self.env['stock.picking'].search(
            [('origin', '=', 'PDA')], order='id desc', limit=1,
        )
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.picking_type_id.code, 'incoming')
        log = self.env['pda.log'].search([
            ('user_id', '=', self.operator.id),
            ('operation', '=', 'receipt'),
        ])
        self.assertEqual(log.state, 'success')
        self.assertAlmostEqual(log.quantity, 5.0)

    def test_issue_removes_stock(self):
        """Une sortie diminue le stock et valide un transfert sortant."""
        result = self._service().issue_product(
            TEST_BARCODE, 2, self.internal_location.id,
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['operation'], 'issue')
        self.assertAlmostEqual(result['total_available_quantity'], 5.0)
        picking = self.env['stock.picking'].search(
            [('origin', '=', 'PDA')], order='id desc', limit=1,
        )
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.picking_type_id.code, 'outgoing')

    def test_issue_insufficient_stock(self):
        """Une sortie supérieure au stock disponible est refusée."""
        error = self._expect_operation_error(
            'issue_product', TEST_BARCODE, 999, self.internal_location.id,
        )

        self.assertEqual(error.error_code, 'insufficient_stock')
        log = self.env['pda.log'].search([
            ('user_id', '=', self.operator.id),
            ('operation', '=', 'issue'),
        ])
        self.assertEqual(log.state, 'error')
        self.assertAlmostEqual(
            self.product.with_context(
                location=self.internal_location.id,
            ).qty_available,
            7.0,
        )

    def test_transfer_moves_quantity(self):
        """Un transfert déplace la quantité entre deux emplacements internes."""
        result = self._service().transfer_product(
            TEST_BARCODE, 3, self.internal_location.id, self.second_location.id,
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['operation'], 'transfer')
        self.assertAlmostEqual(result['total_available_quantity'], 7.0)
        quantities = {
            line['location_id']: line['available_quantity']
            for line in result['locations']
        }
        self.assertAlmostEqual(quantities[self.internal_location.id], 4.0)
        self.assertAlmostEqual(quantities[self.second_location.id], 3.0)
        picking = self.env['stock.picking'].search(
            [('origin', '=', 'PDA')], order='id desc', limit=1,
        )
        self.assertEqual(picking.picking_type_id.code, 'internal')

    def test_transfer_same_location_rejected(self):
        """Un transfert vers l'emplacement source est refusé."""
        error = self._expect_operation_error(
            'transfer_product', TEST_BARCODE, 1,
            self.internal_location.id, self.internal_location.id,
        )

        self.assertEqual(error.error_code, 'invalid_location')

    def test_inventory_sets_counted_quantity(self):
        """Un inventaire fixe la quantité comptée et crée un ajustement."""
        result = self._service().inventory_product(
            TEST_BARCODE, 4, self.internal_location.id,
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['operation'], 'inventory')
        self.assertAlmostEqual(result['total_available_quantity'], 4.0)
        self.assertAlmostEqual(
            self.product.with_context(
                location=self.internal_location.id,
            ).qty_available,
            4.0,
        )

    def test_inventory_zero_clears_stock(self):
        """Un inventaire à zéro vide l'emplacement."""
        result = self._service().inventory_product(
            TEST_BARCODE, 0, self.internal_location.id,
        )

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['total_available_quantity'], 0.0)

    def test_operation_access_denied(self):
        """Un utilisateur hors groupe PDA ne peut pas faire d'opération."""
        try:
            self._service(self.outsider).receive_product(
                TEST_BARCODE, 1, self.internal_location.id,
            )
        except PdaError as error:
            self.assertEqual(error.error_code, 'access_denied')
        else:
            self.fail("Une PdaError était attendue.")

    def test_operation_invalid_quantity(self):
        """Une quantité nulle ou non numérique est refusée."""
        error = self._expect_operation_error(
            'receive_product', TEST_BARCODE, 0, self.internal_location.id,
        )
        self.assertEqual(error.error_code, 'invalid_quantity')


class TestPdaInterface(TransactionCase):
    """Vérifie le câblage serveur de l'écran OWL (action client et menu)."""

    def test_scanner_action_registered(self):
        """L'action client pointe sur le tag OWL enregistré côté JS."""
        action = self.env.ref('pda_base.action_pda_scanner')

        self.assertEqual(action.type, 'ir.actions.client')
        self.assertEqual(action.tag, 'pda_base.scanner')

    def test_scanner_menu_visible_for_operators(self):
        """Le menu Scanner est visible par les opérateurs PDA."""
        menu = self.env.ref('pda_base.menu_pda_scanner')
        action = self.env.ref('pda_base.action_pda_scanner')

        self.assertIn(self.env.ref('pda_base.group_pda_user'), menu.group_ids)
        self.assertEqual(menu.action._name, 'ir.actions.client')
        self.assertEqual(menu.action.id, action.id)
