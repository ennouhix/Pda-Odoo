# odoo-pda

Application mobile de gestion de stock intégrée à **Odoo 19 (Community)**,
livrée en Docker. Le magasinier scanne un code-barres depuis son téléphone ou
une douchette, et Odoo enregistre un transfert de stock standard : pas de
middleware, pas de double saisie.

## Démarrage rapide

```bash
cp .env.example .env    # puis renseigner les mots de passe
./scripts/demo-start.sh
```

Odoo : <http://localhost:8069>, base **pda_demo**.

| Compte | Identifiant | Mot de passe |
| --- | --- | --- |
| Opérateur PDA | `pda.operateur` | `pda.operateur` |
| Responsable PDA | `pda.responsable` | `pda.responsable` |
| Administrateur | `admin` | `admin` |

Guide de démonstration complet (pitch, scénario minuté, roadmap) :
**[docs/DEMO_CLIENT.md](docs/DEMO_CLIENT.md)**.

## Ce que fait l'application

Menu **PDA > Scanner** :

* recherche produit par code-barres (douchette, clavier ou caméra du téléphone) ;
* stock disponible et détail par emplacement interne ;
* opérations **réception**, **sortie**, **transfert** et **inventaire** ;
* erreurs lisibles (code-barres inconnu, stock insuffisant, droits, réseau) ;
* menu **PDA > Journal** pour le responsable : historique horodaté de toutes les
  opérations, succès et erreurs.

## Structure du dépôt

```
addons/custom/
  pda_base/     socle : sécurité, journal, service métier, API JSON-RPC, écran OWL
  pda_demo/     données de démonstration (produits, emplacements, stock, comptes)
config/         odoo.conf
scripts/        demo-start.sh (base de démo prête à présenter)
docs/           DEMO_CLIENT.md (support de présentation)
docker-compose.yml
```

## API

Endpoints `jsonrpc`, session Odoo, groupe `Opérateur PDA` requis :

| Endpoint | Paramètres |
| --- | --- |
| `POST /pda/api/product/by_barcode` | `barcode` |
| `POST /pda/api/locations` | — |
| `POST /pda/api/receipt` | `barcode`, `quantity`, `location_dest_id` |
| `POST /pda/api/issue` | `barcode`, `quantity`, `location_id` |
| `POST /pda/api/transfer` | `barcode`, `quantity`, `location_id`, `location_dest_id` |
| `POST /pda/api/inventory` | `barcode`, `quantity`, `location_id` |

Réponse d'erreur toujours structurée :

```json
{"success": false, "error_code": "unknown_barcode", "message": "..."}
```

Détail des contrats et exemples : [addons/custom/pda_base/README.md](addons/custom/pda_base/README.md).

## Installation sur une base existante

```bash
docker compose up -d
docker compose run --rm odoo odoo -d <base> -i pda_base --stop-after-init
```

Ne pas installer `pda_demo` en dehors des démonstrations.

## Tests

```bash
docker compose run --rm odoo odoo -d pda_dev -u pda_base \
  --test-tags /pda_base --stop-after-init
```

## Limites connues

Pas de lots/numéros de série, pas d'anti-double-scan, un seul entrepôt, caméra
limitée aux contextes HTTPS. Voir la feuille de route dans
[docs/DEMO_CLIENT.md](docs/DEMO_CLIENT.md).
