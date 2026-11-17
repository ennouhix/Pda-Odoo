# PDA Base (Odoo 19.0)

Socle de l'application PDA de scan de codes-barres : sécurité, journal des
opérations, logique métier, API JSON-RPC et premier écran OWL « Scanner »
(recherche par code-barres et consultation du stock).

## Contenu

| Élément | Rôle |
| --- | --- |
| Groupe `group_pda_user` | Opérateur PDA (implique `base.group_user`) |
| Groupe `group_pda_manager` | Responsable PDA (implique `group_pda_user`) |
| Modèle `pda.log` | Journal des opérations (succès et erreurs) |
| Modèle abstrait `pda.service` | Logique métier : lookup produit, emplacements |
| `controllers/main.py` | Endpoints JSON-RPC sécurisés |
| Écran OWL `pda_base.scanner` | Scan, fiche produit, stock par emplacement, emplacements |

## Interface PDA

Menu **PDA > Scanner**, visible par les opérateurs PDA. L'action client OWL
ouvre un écran plein format adapté au mobile :

* champ de scan (validation par `Entrée`, comme la plupart des lecteurs) ;
* fiche produit : référence, nom, quantité disponible totale et détail par
  emplacement interne ;
* opérations de stock : réception, sortie, transfert et inventaire, avec
  quantité et emplacement(s), puis rafraîchissement du stock affiché ;
* erreurs lisibles (code-barres inconnu, droits insuffisants, stock
  insuffisant, quantité invalide, réseau) ;
* panneau « Emplacements » listant les emplacements internes et leur
  code-barres.

Le composant ne contient aucune logique métier : il appelle uniquement les
endpoints JSON-RPC ci-dessous, qui délèguent à `pda.service`.

Fichiers : `static/src/scanner/scanner.js`, `scanner.xml`, `scanner.scss`,
chargés via `web.assets_backend`. L'action client est déclarée dans
`views/pda_scanner_action.xml`.

## Sécurité

Les deux groupes sont rattachés au privilège **PDA** (catégorie `PDA`) visible
dans la fiche utilisateur. Les droits d'accès sont définis dans
`security/ir.model.access.csv`.

Les opérateurs ne disposent que de leurs droits Odoo habituels : le module
n'utilise **jamais** `sudo()` pour la lecture des produits, quantités ou
emplacements. Le seul `sudo()` est réservé à l'écriture du journal `pda.log`,
afin qu'une opération échouée faute de droits soit tout de même tracée.

Les tests HTTP ne nécessitent pas de droit `stock` supplémentaire pour le
lookup : la lecture des produits, `stock.quant` et `stock.location` est
ouverte aux utilisateurs internes par les ACL du module `stock`.

## API JSON-RPC

Les deux endpoints sont de type `jsonrpc`, `auth='user'`, en `POST`, et
exigent le groupe `group_pda_user`. En cas d'erreur, la réponse est toujours un
résultat JSON structuré, sans trace Python :

```json
{"success": false, "error_code": "unknown_barcode", "message": "..."}
```

Codes d'erreur : `invalid_barcode`, `unknown_barcode`, `invalid_quantity`,
`invalid_location`, `insufficient_stock`, `unsupported_tracking`,
`configuration_error`, `validation_failed`, `inventory_conflict`,
`access_denied`, `internal_error`.

### `POST /pda/api/product/by_barcode`

Paramètre : `barcode` (chaîne).

Réponse (extrait) :

```json
{
  "success": true,
  "id": 42,
  "reference": "PDA-TEST-REF",
  "name": "Produit PDA Test",
  "barcode": "PDA-TEST-001",
  "uom": "Units",
  "total_quantity": 7.0,
  "total_available_quantity": 7.0,
  "locations": [
    {
      "location_id": 12,
      "location_name": "WH/Stock/PDA Test Shelf",
      "quantity": 7.0,
      "available_quantity": 7.0
    }
  ]
}
```

Seuls les emplacements internes (`usage = 'internal'`) sont pris en compte.

### `POST /pda/api/locations`

Aucun paramètre. Réponse :

```json
{
  "success": true,
  "locations": [
    {"id": 12, "name": "WH/Stock/PDA Test Shelf", "barcode": ""}
  ]
}
```

### Opérations de stock

Quatre endpoints supplémentaires, avec les mêmes contraintes (`jsonrpc`,
`auth='user'`, `POST`, groupe `group_pda_user`) :

| Endpoint | Paramètres | Effet |
| --- | --- | --- |
| `/pda/api/receipt` | `barcode`, `quantity`, `location_dest_id` | Transfert entrant vers un emplacement interne |
| `/pda/api/issue` | `barcode`, `quantity`, `location_id` | Transfert sortant depuis un emplacement interne |
| `/pda/api/transfer` | `barcode`, `quantity`, `location_id`, `location_dest_id` | Transfert interne entre deux emplacements |
| `/pda/api/inventory` | `barcode`, `quantity`, `location_id` | Quantité comptée (0 autorisé) appliquée en inventaire |

Chaque opération crée et valide un `stock.picking` standard (aucun `sudo()`,
les droits Odoo de l'utilisateur s'appliquent) et renvoie la fiche produit à
jour :

```json
{
  "success": true,
  "operation": "receipt",
  "message": "Réception : 5.0 × Produit PDA Test",
  "id": 42,
  "total_available_quantity": 12.0,
  "locations": []
}
```

Règles métier : quantité strictement positive (sauf inventaire), emplacements
internes uniquement, stock disponible vérifié pour les sorties et transferts,
transfert refusé vers l'emplacement source. Les produits suivis par lot ou
numéro de série sont refusés pour l'instant (`unsupported_tracking`).

**Droits requis** : les opérateurs doivent aussi posséder les droits
Inventaire (`stock.group_stock_user`) pour créer et valider les transferts et
pour appliquer un inventaire. Sans ces droits, l'API renvoie
`access_denied` — le module n'élargit jamais les droits Odoo.

### Journalisation

Chaque appel, réussi ou en erreur, crée une ligne dans `pda.log` avec
l'utilisateur d'origine, l'opération (`lookup`, `receipt`, `issue`,
`transfer`, `inventory`), le code-barres, le produit, l'emplacement, la
quantité, l'état et le message.

## Installation

```bash
cd ~/odoo-pda
docker compose restart odoo
docker compose run --rm odoo odoo -d pda_dev -i pda_base --stop-after-init
```

## Tests

```bash
docker compose run --rm odoo odoo -d pda_dev -u pda_base \
  --test-tags /pda_base --stop-after-init
```

## Exemple d'appel avec session

```bash
curl -s -c /tmp/pda.cookies -X POST http://localhost:8069/web/session/authenticate \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","params":{"db":"pda_dev","login":"admin","password":"admin"}}'

curl -s -b /tmp/pda.cookies -X POST \
  http://localhost:8069/pda/api/product/by_barcode \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"call","params":{"barcode":"PDA-TEST-001"},"id":1}'
```

## Limites connues

* pas de gestion des lots et numéros de série ;
* pas de reliquat (backorder) : la quantité scannée est la quantité validée ;
* pas d'idempotence : un double scan valide deux opérations ;
* un seul entrepôt pris en compte (celui de l'emplacement scanné, sinon le
  premier de la société).

## Suite prévue

Prochaines étapes : prise en charge des lots/numéros de série, anti-double
scan (jeton d'opération), choix de l'entrepôt, et historique des opérations
PDA dans l'écran mobile.
