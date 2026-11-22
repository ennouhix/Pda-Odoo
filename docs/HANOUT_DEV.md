# Hanout Gestion — notes de développement

Reprise du développement du module Odoo 19 `hanout_gest` (boutique de
proximité) et de ses données de démonstration `hanout_demo`.

Guide fonctionnel (utilisateur) : [HANOUT_GUIDE.pdf](HANOUT_GUIDE.pdf),
régénérable avec `python3 scripts/build-hanout-guide.py`.
Référence du module : [../addons/custom/hanout_gest/README.md](../addons/custom/hanout_gest/README.md).

## État actuel

| Élément | Valeur |
| --- | --- |
| Version du module | `19.0.1.2.0` (manifest) |
| Modules | `hanout_gest` (métier), `hanout_demo` (données de test, `noupdate="1"`) |
| Dépendances | `point_of_sale`, `stock` |
| Tests | 31 tests, 0 échec (`--test-tags /hanout_gest`) |
| Base de dev | `hanout_dev` (démo installée) |
| Base « live » | `Odoo_19` sur le conteneur `odoo-pda-web`, port 8069 |

Livré :

- **Lot 1** — magasins, caisse simplifiée, ticket hanout numéroté par magasin,
  dépenses de caisse, clôture journalière, groupes caissier/gérant,
  cloisonnement multi-société.
- **Lot 2** — carnet de crédit : moyen de paiement `pay_later`, plafond par
  client, contrôle à l'encaissement, écran des débiteurs, règlement partiel.

Reste à faire : lots 3 à 6 (voir [Backlog](#backlog)).

## Démarrer

```bash
docker compose up -d

# installer / mettre à jour le module sur la base de dev
docker compose run --rm odoo odoo -d hanout_dev -u hanout_gest \
  --test-tags /hanout_gest --stop-after-init

# mettre à jour la base de démonstration live (service arrêté pendant l'upgrade)
docker compose stop odoo
docker compose run --rm odoo odoo -d Odoo_19 -u hanout_gest --stop-after-init
docker compose start odoo
```

Toujours garder le statut de sortie : `set -o pipefail` quand la sortie passe
dans `grep`/`tee`, sinon un échec de test passe inaperçu.

Comptes : `admin/admin`, `hanout.caissier/hanout.caissier`,
`hanout.gerant/hanout.gerant`.

### Shell Odoo (POC, vérifications, scripts jetables)

```bash
docker cp /tmp/x.py odoo-pda-web:/tmp/x.py
docker exec -i odoo-pda-web sh -c "odoo shell -d hanout_dev --no-http \
  $(tr '\0' '\n' </proc/1/cmdline | awk '/^--db_/{printf \"%s \", \$0; f=1; next} f{printf \"%s \", \$0; f=0}') \
  < /tmp/x.py"
```

Terminer un POC par `env.cr.rollback()` pour ne rien laisser en base.

## Arborescence du module

```
hanout_gest/
  __manifest__.py          version, data, assets point_of_sale._assets_pos
  models/
    hanout_shop.py         hanout.shop : magasin + séquence de ticket
    hanout_expense.py      hanout.expense : dépense de caisse
    hanout_credit_payment.py  hanout.credit.payment : wizard de règlement
    pos_config.py          magasin, mode simplifié, moyen de paiement carnet
    pos_order.py           nom du ticket HCS/2026/000042
    pos_payment.py         contrôle du plafond du carnet
    pos_session.py         dépenses de session, théorique ajusté
    res_partner.py         plafond, solde, crédit en session, règlement
  security/
    hanout_security.xml    catégorie, privilège, groupes caissier/gérant
    hanout_rules.xml       ir.rule société (magasins, dépenses)
    ir.model.access.csv    ACL
  views/                   vues + menus (menus dans hanout_menus.xml)
  migrations/
    19.0.1.1.0/post-migrate.py  séquences de ticket des magasins existants
    19.0.1.1.1/post-migrate.py  retrait du NOT NULL + nettoyage mode simple
  static/src/
    js/hanout_pos.js       classe o_hanout_simple sur le document
    scss/hanout_pos.scss   masquages du mode simplifié
    scss/hanout_receipt.scss  ticket zellige
    xml/hanout_receipt.xml    en-tête/pied du ticket
    xml/hanout_control_buttons.xml  marque le bouton retour (o_hanout_refund)
  tests/test_hanout_gest.py
```

## Modèle de données

```
hanout.shop ──< pos.config >── pos.session ──< pos.order ──< pos.payment
     │              │                │
     │              └── order_seq_id = shop.sequence_id (ir.sequence)
     └──< hanout.expense >── pos.session
res.partner : hanout_credit_limit / _balance / _pending / _available
```

| Modèle | Champs et comportements clés |
| --- | --- |
| `hanout.shop` | `name`, `code` (unique/société), `company_id`, `warehouse_id`, `phone`, `address`, `sequence_id`, `pos_config_ids`. `create` crée la séquence `CODE/%(range_year)s/` (padding 6) ; `write` sur `code` met à jour le préfixe. `action_hanout_open_pos()` ouvre la caisse unique ou liste les caisses. |
| `hanout.expense` | `name`, `category` (7 valeurs), `amount` > 0, `date`, `shop_id` obligatoire (défaut = magasin unique), `session_id`, `user_id`, `note`. Refus si session `closed` ; société du magasin = société de la dépense. |
| `pos.config` | `hanout_shop_id`, `hanout_simple_mode`, `_hanout_ensure_credit_method()`, `_hanout_use_shop_sequence()`, `action_hanout_apply_simple_mode()`. |
| `pos.session` | `hanout_shop_id` (related stocké), `hanout_expense_ids`, `hanout_expense_total`, `_compute_cash_balance` diminué des dépenses, `action_hanout_view_expenses()`. |
| `pos.order` | `_get_order_name_from_pos_reference()` : `préfixe + numéro` sans le « - » d'Odoo. |
| `pos.payment` | `_hanout_check_credit_limit(values)` appelé **avant** `create`. |
| `res.partner` | Plafond, solde comptable, crédit en session, disponible, `_search_hanout_credit_balance`, `action_hanout_register_credit_payment()`. |
| `hanout.credit.payment` | Wizard : `partner_id`, `balance`, `pending`, `amount`, `journal_id`, `payment_date`, `reference`. `action_register()` crée et valide un `account.payment` client puis réconcilie les créances ouvertes (FIFO). |

## Décisions techniques (et pourquoi)

1. **Crédit = `pay_later` natif, pas de carnet maison.** Un
   `pos.payment.method` sans journal et `split_transactions=True`. La créance
   part sur le compte client du partenaire à la clôture de session
   (`_create_pay_later_receivable_lines`). Sans `split_transactions`, la
   créance tombe sur le compte d'attente POS sans client : vérifié en base,
   aucun solde suivi.
2. **Solde = comptabilité + crédit en session.** `hanout_credit_balance`
   (créances postées non réconciliées) et `hanout_credit_pending` (paiements
   `pay_later` des sessions `opening_control`/`opened`). Le contrôle de
   plafond additionne les deux ; le règlement ne travaille que sur la partie
   comptable, d'où la limite documentée « pas de règlement avant clôture ».
3. **Numérotation par magasin, pas par caisse.** `pos.config` n'a pas de
   `sequence_id` : la séquence du ticket est `order_seq_id`, créée par
   `_create_sequences()`. On la remplace par `hanout.shop.sequence_id` et on
   désactive l'ancienne si elle n'a jamais servi (`number_next_actual == 1`).
   Le nom du ticket est reconstruit depuis `pos_reference` (dernier segment)
   et le préfixe de `order_seq_id`.
4. **Magasin de caisse : contrainte Python, pas SQL.** La base live contenait
   des caisses Point de Vente historiques sans magasin, donc `required=True`
   échouait (`column ... contains null values`). Le champ reste nullable en
   base, la règle « mode simplifié ⇒ magasin » est un `@api.constrains`, et
   `create` active le mode simplifié dès qu'un magasin est fourni.
5. **Mode simplifié = classe CSS, pas de fork de l'interface.** Le JS pose
   `o_hanout_simple` sur `<body>`, le SCSS masque pavé/actions/raccourcis et
   agrandit les cibles. Le retour client est marqué dans la fenêtre « Autres
   actions » par héritage de template, avec un repli CSS
   `:not(:has(.fa-undo))`.
6. **Contrôle du plafond avant écriture.** `pos.payment.create` valide les
   `vals_list` puis appelle `super()` : un refus ne laisse aucun paiement en
   base, ce qui évite les demi-écritures si l'appelant attrape l'erreur.

## Pièges Odoo 19 rencontrés

| Piège | Conséquence / solution |
| --- | --- |
| `pos.config.write` refuse de modifier `payment_method_ids` si `has_active_session` | Fermer la caisse avant `action_hanout_apply_simple_mode` (message explicite ajouté). En test, créer une caisse dédiée sans session. |
| Champ calculé non stocké dans un domaine SQL (`payment_method_id.type`) | `ValueError: Cannot convert ... to SQL`. Utiliser `('payment_method_id.journal_id', '=', False)` : type `pay_later` ⇔ pas de journal. |
| `account.account` n'a pas `company_id` en 19 | `company_ids` (Many2many). Une recherche `('company_id', '=', ...)` casse. |
| `_read_group` sur un champ related non stocké | Passer par `search()` + agrégation Python pour `pos_order_id.partner_id`. |
| Champs calculés non stockés en cache | Un solde lu deux fois dans la même transaction peut être périmé : `partner.invalidate_recordset()` avant lecture après création d'un paiement. |
| `ensure_one()` dans un helper appelé depuis `compute`/`search` | Le recordset peut contenir plusieurs clients (`too many values to unpack`). Ne pas mettre `ensure_one` dans `_hanout_credit_balances()`/`_hanout_credit_pending_amounts()`. |
| `pos.order.create` exige `amount_tax/amount_total/amount_paid/amount_return` explicites en 19 | Les fournir dans les tests et POC. |
| `pos.order.name` reste `/` à la création | Le nom vient de `pos_reference` : à vérifier via `_get_order_name_from_pos_reference()`, pas à la création ORM. |
| `noupdate="1"` sur `hanout_demo` | Modifier une donnée existante du fichier ne s'applique pas aux bases déjà installées. Le moyen de paiement carnet ajouté à la caisse démo n'existe donc que sur une installation neuve : sur une base existante, cliquer « Appliquer le mode hanout simple » (caisse fermée). |
| Base de dev avec session POS ouverte | Bloque les écritures de configuration (moyens de paiement, caisse). Fermer ou créer une caisse de test. |

## Conventions du dépôt

- **Français partout** : code, commentaires, libellés, messages d'erreur,
  README. Chaînes utilisateur via `_()`.
- Licence `LGPL-3`, auteur `Odoo PDA`, catégorie `Sales/Point of Sale`.
- Odoo 19 : `models.Constraint` pour les contraintes SQL, `<list>` dans les
  vues, `Command` pour les x2many, `invisible="expr"` (pas d'`attrs`).
- Version `19.0.1.X.Y` : incrémenter à chaque livraison, et ajouter une
  migration `migrations/<version>/post-migrate.py` dès qu'une donnée existante
  doit être reprise.
- Couche métier mince : ne pas dupliquer Odoo (vente, stock, comptabilité).

## Ajouter une fonctionnalité — checklist

1. Modèle dans `models/`, `_inherit` si Odoo fournit déjà l'objet, import dans
   `models/__init__.py`.
2. ACL dans `security/ir.model.access.csv` (caissier : lecture/écriture,
   gérant : tout) et `ir.rule` société si le modèle porte `company_id`.
3. Vues dans `views/`, entrée de menu dans `views/hanout_menus.xml`, fichiers
   ajoutés à `data` du manifest.
4. Tests dans `tests/test_hanout_gest.py` (hériter de `HanoutTestDataMixin`
   pour disposer du magasin, de la caisse et de la session).
5. Migration si des données existantes changent, bump de version.
6. README du module + ce fichier (et guide PDF si c'est visible utilisateur :
   `python3 scripts/build-hanout-guide.py`).

## Tests

```bash
set -o pipefail
docker compose run --rm odoo odoo -d hanout_dev -u hanout_gest \
  --test-tags /hanout_gest --stop-after-init 2>&1 | tee /tmp/t.log \
  | grep -E "tests.result|FAIL:|ERROR: Test"
```

Classes : `TestHanoutShop`, `TestHanoutOpenPos`,
`TestHanoutTicketSequence`, `TestHanoutCompanyRules`, `TestHanoutExpense`,
`TestHanoutCredit`. Les `ERROR: duplicate key ...` et
`null value in column "name"` du log sont attendus (`assertRaises` sur
`IntegrityError`).

`HanoutTestDataMixin` crée un journal bancaire si la base n'en a pas, un
magasin `HT`, une caisse et une session ouverte. `TestHanoutCredit` crée en
plus une caisse dédiée (sans session) pour y brancher le moyen de paiement
carnet, et une facture client postée pour tester la réconciliation.

## Backlog

| Lot | Contenu | Notes de mise en œuvre |
| --- | --- | --- |
| 3 | Alertes de rupture en caisse, réappro, inventaire rapide par scan | Réutiliser `pda_base` (service de scan, `stock.quant`) ; badges de seuil `product.reordering_min_qty` dans les tuiles POS. |
| 4 | Achats fournisseurs et réception guidée | `purchase.order` natif + écran simplifié, pas de nouveau modèle d'achat. |
| 5 | Tableau de bord gérant : CA, marge, top produits, dettes | Vues `pos.order`/`account.move.line` en graph/pivot, ou tableau de bord OWL dédié. |
| 6 | Industrialisation | Sauvegardes, script d'upgrade, formation caissier, jeu de tests sur base vierge. |

Dettes techniques identifiées :

- **Contrôle du plafond dans l'écran POS** avant validation (patch OWL de
  l'écran de paiement, en s'appuyant sur `hanout_credit_available` chargé
  côté POS). Aujourd'hui le refus arrive au moment de l'enregistrement.
- **Règlement du crédit d'une session ouverte** : impossible avant clôture
  (la créance n'existe pas encore). Une piste serait de lettrer les créances
  à la clôture de session.
- **Moyen de paiement carnet sur les bases existantes** : prévoir une
  migration ou une action de masse plutôt que le bouton manuel.
- **Rapports** : aucun rapport dédié (ventes, dépenses, dettes) ; tout passe
  par les vues standard.
- **Vérification visuelle** : le mode simplifié et le bouton retour ont été
  vérifiés au niveau du bundle (CSS/JS) et du template, pas cliqués dans un
  navigateur réel.

## Liens utiles

- Guide fonctionnel PDF : [HANOUT_GUIDE.pdf](HANOUT_GUIDE.pdf)
  (`scripts/build-hanout-guide.py`)
- README du module : [../addons/custom/hanout_gest/README.md](../addons/custom/hanout_gest/README.md)
- Démo hanout : [../addons/custom/hanout_demo/README.md](../addons/custom/hanout_demo/README.md)
- Démo générale du dépôt : [DEMO_CLIENT.md](DEMO_CLIENT.md)
