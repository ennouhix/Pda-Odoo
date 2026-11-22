# -*- coding: utf-8 -*-
"""Tests du module hanout_gest (magasin, dépenses et clôture de caisse)."""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class HanoutTestDataMixin:
    """Données partagées : un magasin, sa caisse et une session ouverte."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # La création d'une caisse POS exige un journal bancaire, que la base
        # de test ne possède pas tant qu'aucun plan comptable n'est installé.
        if not cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1):
            cls.env['account.journal'].create({
                'name': 'Banque test',
                'type': 'bank',
                'code': 'BNKT',
            })
        cls.shop = cls.env['hanout.shop'].create({
            'name': 'Hanout Test',
            'code': 'HT',
        })
        cls.config = cls.env['pos.config'].create({
            'name': 'Caisse Test',
            'hanout_shop_id': cls.shop.id,
        })
        cls.session = cls.env['pos.session'].create({
            'config_id': cls.config.id,
            'user_id': cls.env.uid,
        })


class TestHanoutShop(HanoutTestDataMixin, TransactionCase):
    """Tests du modèle ``hanout.shop``."""

    def test_shop_links_config_and_session(self):
        """La caisse et sa session sont rattachées au magasin hanout."""
        self.assertEqual(self.config.hanout_shop_id, self.shop)
        self.assertIn(self.config, self.shop.pos_config_ids)
        self.assertEqual(self.session.hanout_shop_id, self.shop)

    def test_shop_identity_available_on_ticket(self):
        """Le ticket de caisse reprend l'identité du magasin hanout."""
        self.shop.write({
            'phone': '06 12 34 56 78',
            'address': '12 rue du marché',
        })

        self.assertEqual(self.config.hanout_shop_name, self.shop.name)
        self.assertEqual(self.config.hanout_shop_phone, '06 12 34 56 78')
        self.assertEqual(self.config.hanout_shop_address, '12 rue du marché')

    def test_simple_mode_applies_cash_fast_payment(self):
        """Le mode simplifié règle la caisse et branche le paiement rapide espèces."""
        # Ces réglages ne sont modifiables que caisse fermée : on utilise une
        # seconde caisse sans session ouverte.
        config = self.env['pos.config'].create({
            'name': 'Caisse simple',
            'hanout_shop_id': self.shop.id,
        })
        cash_journal = self.env['account.journal'].create({
            'name': 'Caisse simple',
            'type': 'cash',
            'code': 'CSHT',
        })
        cash_method = self.env['pos.payment.method'].create({
            'name': 'Espèces simple',
            'journal_id': cash_journal.id,
        })
        config.write({
            'payment_method_ids': [(4, cash_method.id)],
            'hanout_simple_mode': False,
        })

        config.action_hanout_apply_simple_mode()

        self.assertTrue(config.hanout_simple_mode)
        self.assertTrue(config.use_fast_payment)
        self.assertEqual(config.fast_payment_method_ids, cash_method)
        self.assertFalse(config.manual_discount)

    def test_config_with_shop_enables_simple_mode(self):
        """Rattacher une caisse à un magasin active le mode simplifié."""
        config = self.env['pos.config'].create({
            'name': 'Caisse auto',
            'hanout_shop_id': self.shop.id,
        })

        self.assertTrue(config.hanout_simple_mode)

    def test_config_simple_mode_requires_shop(self):
        """Une caisse en mode hanout sans magasin est refusée."""
        with self.assertRaises(ValidationError):
            self.env['pos.config'].create({
                'name': 'Caisse hors magasin',
                'hanout_simple_mode': True,
            })

    def test_config_without_shop_stays_standard(self):
        """Une caisse Point de Vente classique reste possible."""
        config = self.env['pos.config'].create({
            'name': 'Caisse standard',
        })

        self.assertFalse(config.hanout_simple_mode)
        self.assertFalse(config.hanout_shop_id)

    def test_shop_code_unique_per_company(self):
        """Deux magasins ne peuvent pas partager le même code."""
        with self.assertRaises(IntegrityError):
            self.env['hanout.shop'].create({
                'name': 'Autre hanout',
                'code': 'HT',
            })


class TestHanoutOpenPos(HanoutTestDataMixin, TransactionCase):
    """Démarrage de la caisse depuis le module hanout."""

    def test_open_pos_without_config_raises(self):
        """Un magasin sans caisse explique quoi faire au lieu de planter."""
        shop = self.env['hanout.shop'].create({
            'name': 'Hanout sans caisse',
            'code': 'HSC',
        })

        with self.assertRaises(UserError):
            shop.action_hanout_open_pos()

    def test_open_pos_opens_the_only_config(self):
        """Avec une seule caisse, le bouton ouvre directement l'interface POS."""
        self.shop.pos_config_ids = [(6, 0, self.config.ids)]

        action = self.shop.action_hanout_open_pos()

        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('/pos/ui/%d' % self.config.id, action['url'])

    def test_open_pos_lets_choose_between_configs(self):
        """Avec plusieurs caisses, le bouton propose le choix du magasin."""
        second = self.env['pos.config'].create({
            'name': 'Caisse secondaire',
            'hanout_shop_id': self.shop.id,
        })

        action = self.shop.action_hanout_open_pos()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'pos.config')
        self.assertIn(second.id, action['domain'][0][2])


class TestHanoutTicketSequence(HanoutTestDataMixin, TransactionCase):
    """Numérotation des tickets par magasin."""

    def test_shop_gets_ticket_sequence(self):
        """Créer un magasin crée sa séquence de ticket préfixée par son code."""
        self.assertTrue(self.shop.sequence_id)
        self.assertEqual(self.shop.sequence_id.prefix, 'HT/%(range_year)s/')
        self.assertEqual(self.shop.sequence_id.padding, 6)

    def test_config_uses_shop_sequence(self):
        """La caisse imprime ses tickets avec la séquence du magasin."""
        self.assertEqual(self.config.order_seq_id, self.shop.sequence_id)

    def test_two_configs_share_shop_sequence(self):
        """Deux caisses du même magasin partagent la numérotation."""
        second = self.env['pos.config'].create({
            'name': 'Caisse deuxième',
            'hanout_shop_id': self.shop.id,
        })

        self.assertEqual(second.order_seq_id, self.shop.sequence_id)
        self.assertEqual(second.order_seq_id, self.config.order_seq_id)

    def test_ticket_name_uses_shop_sequence(self):
        """Le ticket est nommé HCS/2026/000007 : magasin, année, numéro."""
        order = self.env['pos.order'].create({
            'session_id': self.session.id,
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        })
        order.pos_reference = '260-1-000007'

        name = order._get_order_name_from_pos_reference()

        self.assertTrue(name.startswith('HT/'))
        self.assertTrue(name.endswith('/000007'))
        self.assertNotIn(' - ', name)

    def test_shop_code_change_updates_sequence_prefix(self):
        """Renommer le code du magasin met à jour le préfixe des tickets."""
        self.shop.code = 'HTC'

        self.assertEqual(self.shop.sequence_id.prefix, 'HTC/%(range_year)s/')


class TestHanoutCompanyRules(HanoutTestDataMixin, TransactionCase):
    """Cloisonnement des données hanout par société."""

    def test_shop_and_expense_are_society_scoped(self):
        """Un utilisateur ne voit pas les magasins ni dépenses de l'autre société."""
        company_b = self.env['res.company'].create({'name': 'Hanout B'})
        shop_b = self.env['hanout.shop'].with_company(company_b).create({
            'name': 'Hanout B',
            'code': 'HB',
            'company_id': company_b.id,
        })
        expense_b = self.env['hanout.expense'].with_company(company_b).create({
            'name': 'Dépense B',
            'amount': 10.0,
            'shop_id': shop_b.id,
            'company_id': company_b.id,
        })
        user = self.env['res.users'].create({
            'name': 'Gérant société A',
            'login': 'gerant.societe.a@hanout.test',
            'company_id': self.shop.company_id.id,
            'company_ids': [(6, 0, self.shop.company_id.ids)],
            'group_ids': [(6, 0, [
                self.env.ref('hanout_gest.group_hanout_gerant').id,
            ])],
        })

        shops = self.env['hanout.shop'].with_user(user).search([])
        expenses = self.env['hanout.expense'].with_user(user).search([])

        self.assertIn(self.shop, shops)
        self.assertNotIn(shop_b, shops)
        self.assertNotIn(expense_b, expenses)


class TestHanoutExpense(HanoutTestDataMixin, TransactionCase):
    """Tests du modèle ``hanout.expense``."""

    def _create_expense(self, **values):
        """Créer une dépense minimale sur la session de test."""
        defaults = {
            'name': 'Livraison boissons',
            'amount': 15.0,
            'shop_id': self.shop.id,
            'session_id': self.session.id,
        }
        defaults.update(values)
        return self.env['hanout.expense'].create(defaults)

    def test_expense_defaults_to_single_shop(self):
        """Une société à un seul magasin pré-remplit la dépense."""
        company = self.env['res.company'].create({'name': 'Hanout mono-magasin'})
        shop = self.env['hanout.shop'].with_company(company).create({
            'name': 'Hanout unique',
            'code': 'HU',
            'company_id': company.id,
        })

        expense = self.env['hanout.expense'].with_company(company).create({
            'name': 'Café',
            'amount': 3.0,
        })

        self.assertEqual(expense.shop_id, shop)

    def test_expense_shop_must_belong_to_company(self):
        """Le magasin d'une dépense doit appartenir à sa société."""
        company_b = self.env['res.company'].create({'name': 'Hanout C'})
        shop_b = self.env['hanout.shop'].with_company(company_b).create({
            'name': 'Hanout C',
            'code': 'HC',
            'company_id': company_b.id,
        })

        with self.assertRaises(ValidationError):
            self._create_expense(shop_id=shop_b.id)

    def test_expense_amount_must_be_positive(self):
        """Un montant nul ou négatif est refusé."""
        with self.assertRaises(ValidationError):
            self._create_expense(amount=0)
        with self.assertRaises(ValidationError):
            self._create_expense(amount=-5)

    def test_expense_requires_label(self):
        """Le libellé de la dépense est obligatoire."""
        with self.assertRaises(IntegrityError):
            self._create_expense(name=False)

    def test_expense_total_on_session(self):
        """Le total des dépenses de la session est la somme des montants."""
        self._create_expense(amount=15.0)
        self._create_expense(name='Transport', amount=5.0)

        self.assertEqual(self.session.hanout_expense_total, 20.0)
        self.assertEqual(len(self.session.hanout_expense_ids), 2)

    def test_expense_rejected_on_closed_session(self):
        """Une dépense ne peut pas être ajoutée après clôture."""
        self.session.state = 'closed'
        with self.assertRaises(ValidationError):
            self._create_expense()

    def test_cash_balance_deducts_expenses(self):
        """Le théorique de caisse est diminué des dépenses hanout."""
        self.assertTrue(self.session.cash_control)
        self.session.cash_register_balance_start = 100.0
        self._create_expense(amount=20.0)

        self.assertEqual(self.session.cash_register_balance_end, 80.0)


class TestHanoutCredit(HanoutTestDataMixin, TransactionCase):
    """Carnet de crédit client : plafond, solde et règlements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Les moyens de paiement d'une caisse ne sont modifiables que caisse
        # fermée : on prépare une caisse dédiée au carnet, sans session.
        cls.credit_config = cls.env['pos.config'].create({
            'name': 'Caisse carnet',
            'hanout_shop_id': cls.shop.id,
        })
        cls.credit_method = cls.credit_config._hanout_ensure_credit_method()
        cls.credit_config.write({
            'payment_method_ids': [(4, cls.credit_method.id)],
        })
        cls.credit_session = cls.env['pos.session'].create({
            'config_id': cls.credit_config.id,
            'user_id': cls.env.uid,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Client Carnet',
            'hanout_credit_limit': 100.0,
        })

    def _create_credit_order(self, amount, partner=None):
        """Créer un ticket payé avec le moyen de paiement « Crédit carnet »."""
        partner_id = self.partner.id if partner is None else (partner.id if partner else False)
        order = self.env['pos.order'].create({
            'session_id': self.credit_session.id,
            'partner_id': partner_id,
            'amount_tax': 0.0,
            'amount_total': amount,
            'amount_paid': amount,
            'amount_return': 0.0,
        })
        self.env['pos.payment'].create({
            'pos_order_id': order.id,
            'amount': amount,
            'payment_method_id': self.credit_method.id,
        })
        return order

    def _create_invoice(self, amount):
        """Créer une créance comptable ouverte au nom du client."""
        receivable = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        if not receivable:
            self.skipTest("Plan comptable absent de la base de test")
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Vente à crédit',
                'quantity': 1.0,
                'price_unit': amount,
            })],
        })
        move.action_post()
        return move

    def test_credit_method_is_customer_account(self):
        """Le moyen de paiement carnet est un compte client sans journal."""
        self.assertEqual(self.credit_method.type, 'pay_later')
        self.assertFalse(self.credit_method.journal_id)
        self.assertTrue(self.credit_method.split_transactions)

    def test_credit_sale_within_limit(self):
        """Une vente à crédit dans le plafond est acceptée."""
        self._create_credit_order(40.0)
        self.partner.invalidate_recordset()

        self.assertEqual(self.partner.hanout_credit_pending, 40.0)
        self.assertEqual(self.partner.hanout_credit_available, 60.0)

    def test_credit_sale_above_limit_refused(self):
        """Une vente à crédit qui dépasse le plafond est refusée."""
        self._create_credit_order(80.0)

        with self.assertRaises(UserError):
            self._create_credit_order(30.0)

    def test_credit_sale_without_partner_refused(self):
        """Le carnet exige un client nommé."""
        with self.assertRaises(UserError):
            self._create_credit_order(10.0, partner=False)

    def test_credit_without_limit_is_allowed(self):
        """Sans plafond renseigné, le carnet est illimité."""
        self.partner.hanout_credit_limit = 0.0

        self._create_credit_order(500.0)
        self.partner.invalidate_recordset()

        self.assertEqual(self.partner.hanout_credit_pending, 500.0)
        self.assertEqual(self.partner.hanout_credit_available, 0.0)

    def test_credit_payment_partially_reconciles_debt(self):
        """Un règlement partiel réduit la dette du client."""
        self._create_invoice(40.0)
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        wizard = self.env['hanout.credit.payment'].create({
            'partner_id': self.partner.id,
            'amount': 25.0,
            'journal_id': journal.id,
        })

        wizard.action_register()
        self.partner.invalidate_recordset()

        self.assertAlmostEqual(self.partner.hanout_credit_balance, 15.0, places=2)

    def test_credit_payment_above_balance_refused(self):
        """Un règlement supérieur au solde est refusé."""
        self._create_invoice(40.0)
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        wizard = self.env['hanout.credit.payment'].create({
            'partner_id': self.partner.id,
            'amount': 50.0,
            'journal_id': journal.id,
        })

        with self.assertRaises(UserError):
            wizard.action_register()

    def test_debtor_search_lists_indebted_partner(self):
        """L'écran des débiteurs retrouve les clients qui doivent de l'argent."""
        self._create_invoice(40.0)

        debtors = self.env['res.partner'].search([
            ('hanout_credit_balance', '>', 0),
        ])

        self.assertIn(self.partner, debtors)
