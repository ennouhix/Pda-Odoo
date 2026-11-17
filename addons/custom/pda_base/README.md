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
* erreurs lisibles (code-barres inconnu, droits insuffisants, réseau) ;
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

Codes d'erreur : `invalid_barcode`, `unknown_barcode`, `access_denied`,
`internal_error`.

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

### Journalisation

Chaque appel, réussi ou en erreur, crée une ligne dans `pda.log` avec
l'utilisateur d'origine, l'opération (`lookup` pour les deux endpoints), le
code-barres, le produit, l'état et le message.

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

## Suite prévue

Les opérations `receipt`, `issue`, `transfer` et `inventory` sont déjà
présentes dans la sélection `pda.log.operation` mais ne sont pas encore
implémentées côté service ni exposées dans l'écran OWL. Les prochaines étapes
sont leur implémentation métier, puis leurs écrans de validation (quantités,
emplacement destination, confirmation).
