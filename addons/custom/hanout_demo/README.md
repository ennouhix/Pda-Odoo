# Hanout Demo

Données de test pour la caisse **Hanout Gestion** (Odoo 19). À n'installer que
sur une base de développement : le module crée des comptes avec des mots de
passe connus.

## Contenu

| Élément | Détail |
| --- | --- |
| Comptes | `hanout.caissier` / `hanout.caissier` (Caissier Hanout), `hanout.gerant` / `hanout.gerant` (Gérant Hanout) |
| Magasin | *Hanout Casablanca* (code `HCS`), téléphone et adresse renseignés pour le ticket |
| Caisse | *Caisse Hanout Casablanca*, mode hanout simplifié, paiement rapide en espèces (`Espèces`) |
| Catalogue | 8 articles d'épicerie avec prix et codes-barres, catégorie POS *Épicerie* |
| Dépenses | *Livraison boissons* (80) et *Facture d'électricité* (150) |

## Installation

```bash
docker compose run --rm odoo odoo -d hanout_dev -i hanout_demo --stop-after-init
```

Les données sont créées en `noupdate="1"` : une mise à jour du module ne les
écrase pas, et la désinstallation supprime ce que le module a créé.

## Utilisation

1. Se connecter avec `hanout.caissier`.
2. **Hanout > Caisse > Ouvrir la caisse**, puis **Open Register**.
3. Encaisser quelques articles, constater le ticket hanout (nom, adresse et
   téléphone du magasin, « Merci de votre visite ! »).
4. **Hanout > Caisse > Dépenses** : les deux dépenses d'exemple réduisent le
   théorique de caisse à la clôture.
