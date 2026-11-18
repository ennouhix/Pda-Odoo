# Guide de démonstration client — PDA Stock pour Odoo 19

Application mobile de gestion de stock, intégrée nativement à Odoo.
Ce document sert de support de présentation : pitch, scénario de démo minuté,
architecture et feuille de route.

---

## 1. Le pitch (30 secondes)

> « Vos magasiniers scannent sur le terrain, Odoo enregistre en temps réel.
> Pas de licence tierce, pas de ressaisie au bureau, pas d'écart d'inventaire
> inexpliqué : chaque scan devient un document de stock standard, tracé et
> auditable. »

Trois arguments qui font la différence face à une solution PDA classique :

| Sujet | Solution classique | Ce projet |
| --- | --- | --- |
| Intégration | middleware / connecteur facturé | module Odoo natif, dépendance unique `stock` |
| Matériel | terminal propriétaire + licence | n'importe quel smartphone/tablette, douchette USB/Bluetooth ou caméra |
| Traçabilité | export Excel | `stock.picking` + journal PDA horodaté par utilisateur |
| Coût de démarrage | projet de plusieurs semaines | module installé en une commande |

---

## 2. Le problème que vit le client

* l'inventaire se fait sur papier puis est ressaisi : erreurs et retard ;
* le stock Odoo diverge du stock physique, les réapprovisionnements sont faux ;
* les terminaux PDA industriels sont chers et difficiles à déployer ;
* aucune traçabilité : impossible de savoir qui a bougé quoi, ni quand ;
* les erreurs de scan sont silencieuses (mauvais produit, quantité invalide).

## 3. La solution livrée

| Fonction | Bénéfice client |
| --- | --- |
| Scan par code-barres (douchette ou caméra) | geste naturel, zéro saisie |
| Fiche produit instantanée + stock par emplacement | le magasinier voit où est la marchandise |
| Réception, sortie, transfert, inventaire | les 4 opérations du quotidien |
| Transferts Odoo standards créés et validés | rapports, valorisation et comptabilité inchangés |
| Journal PDA (succès **et** erreurs) | audit et diagnostic simples |
| Groupes Opérateur / Responsable | chacun voit ce qu'il doit voir |
| API JSON-RPC documentée | réutilisable par une appli tierce ou un portail |

---

## 4. Architecture

```
   Smartphone / PDA / douchette
              │  JSON-RPC (session Odoo)
              ▼
   Contrôleurs  /pda/api/*
              ▼
   pda.service  ── validation métier, contrôle d'accès
              ▼
   stock.picking / stock.quant  (standard Odoo)
              ▼
          PostgreSQL
```

* `pda_base` — socle : sécurité, journal, service métier, API, écran OWL.
* `pda_demo` — jeu de données de démonstration (produits, emplacements, stock,
  comptes). Installable et désinstallable sans toucher au reste.

Aucune duplication de la logique de stock : le module crée de vrais transferts
Odoo, donc rien à réconcilier avec la comptabilité ou la valorisation.

---

## 5. Scénario de démonstration (10 minutes)

### Préparation (une seule fois)

```bash
./scripts/demo-start.sh
```

Ouvre <http://localhost:8069>, base **pda_demo**.

| Compte | Identifiant | Mot de passe |
| --- | --- | --- |
| Opérateur PDA | `pda.operateur` | `pda.operateur` |
| Responsable PDA | `pda.responsable` | `pda.responsable` |

Codes-barres de démonstration :

| Code-barres | Produit | Stock initial |
| --- | --- | --- |
| `2000000000015` | Vis inox M6 x 40 — boîte de 100 | 240 (A1) |
| `2000000000022` | Écrou inox M6 — boîte de 200 | 180 (A1) |
| `2000000000039` | Perceuse sans fil 18 V | 12 (A2) |
| `2000000000046` | Batterie 18 V 4 Ah | 25 (A2) |
| `2000000000053` | Gants de protection taille L | 60 (B1) |
| `2000000000060` | Casque de chantier — blanc | 40 (B1) |

Emplacements : `LOC-ZONE-A`, `LOC-A1`, `LOC-A2`, `LOC-B1`.

### Le parcours à montrer

1. **Connexion** avec `pda.operateur`, puis menu **PDA > Scanner**.
   L'écran est plein format, gros boutons, pensé pour un usage debout avec une
   douchette ou un téléphone.

2. **Scan** de `2000000000015` (ou saisie + Entrée).
   → Fiche produit : référence, nom, **240 disponible**, détail par emplacement
   (A1).

3. **Réception** : 24 unités vers « B1 — Réserve ». Valider.
   → Total 264, la ligne B1 apparaît. Le transfert entrant est créé et validé
   dans Odoo, sans assistant.

4. **Transfert** : 12 unités de A1 vers B1.
   → A1 = 228, B1 = 36. Un `stock.picking` interne est créé.

5. **Sortie** : 5 unités depuis A1.
   → A1 = 223.

6. **Inventaire** : scanner `2000000000053` (Gants), emplacement B1, quantité
   comptée `55` au lieu de 60.
   → L'écart est appliqué immédiatement, sans feuille d'inventaire papier.

7. **Côté Odoo (preuve d'intégration)** : Inventaire > Opérations > Transferts,
   filtrer sur l'origine `PDA` : les opérations de la démo y figurent, validées.
   Puis Produits > Vis inox : quantités à jour par emplacement.

8. **Gestion d'erreur** : scanner `9999999999999`.
   → Message lisible « Aucun produit ne correspond au code-barres… », code
   `unknown_barcode`, **aucune trace technique** affichée. L'erreur est
   journalisée.

9. **Journal** : se reconnecter avec `pda.responsable`, menu **PDA > Journal**.
   → Historique complet : utilisateur, date, opération, produit, emplacement,
   quantité, succès/erreur. C'est la réponse à « qui a bougé quoi ? ».

10. **Sécurité** : un utilisateur sans le groupe PDA n'a ni menu ni écran, et
    l'API lui répond `access_denied` (démontrable avec un compte standard).

### Option caméra

Sur téléphone, le bouton caméra utilise le scanner natif d'Odoo. Il exige un
contexte sécurisé : **HTTPS** ou `localhost`. En démo sur le réseau local en
HTTP, la douchette USB/Bluetooth ou la saisie clavier fonctionne parfaitement —
le dire avant la démo évite une mauvaise surprise.

---

## 6. Points à mettre en avant côté technique

* **22 tests automatisés** (service, API HTTP, opérations de stock, câblage de
  l'écran) : `docker compose run --rm odoo odoo -d pda_dev -u pda_base --test-tags /pda_base --stop-after-init`.
* **Aucun `sudo()` métier** : l'opérateur n'obtient que ses droits Odoo réels ;
  le seul `sudo()` sert à journaliser une opération refusée.
* **Erreurs structurées** : `error_code` + message traduit, jamais de traceback
  renvoyé au client.
* **Validation métier centralisée** : quantités, emplacements internes, stock
  disponible, société, type de produit. Le contrôleur HTTP reste mince.
* **Standards Odoo respectés** : `stock.picking` validés, donc rapports,
  valorisation et comptabilité fonctionnent sans adaptation.
* **Interface OWL** : réactive, sans dépendance front supplémentaire, scanner
  caméra natif.

---

## 7. Limites assumées (à dire clairement)

* produits suivis par **lot / numéro de série** : non pris en charge ;
* pas d'**idempotence** : un double scan valide deux opérations ;
* **un entrepôt** à la fois (celui de l'emplacement scanné) ;
* mode **hors-ligne** non prévu : l'application suppose le réseau ;
* caméra uniquement en **HTTPS** (contrainte navigateur, pas du projet).

## 8. Feuille de route proposée

| Phase | Contenu | Valeur |
| --- | --- | --- |
| 2 | lots / numéros de série, anti-double-scan | conforme aux produits tracés |
| 3 | impression d'étiquettes codes-barres depuis Odoo | autonomie du magasin |
| 4 | multi-entrepôt + choix de l'entrepôt à la connexion | déploiement multi-sites |
| 5 | PWA hors-ligne et synchronisation | zones sans réseau |
| 6 | tableau de bord des opérations PDA | pilotage |

## 9. Mise en production — checklist

1. Reverse proxy **HTTPS** (Caddy, Traefik ou Nginx) devant Odoo.
2. Mots de passe PostgreSQL et `admin_passwd` uniques, `.env` non versionné.
3. Sauvegardes automatiques (`pg_dump` + volume Odoo).
4. Comptes nominatifs, groupes **Opérateur PDA** / **Responsable PDA**.
5. Déployer `pda_base` sur la base du client, **sans** `pda_demo`.
6. Lancer les tests sur une copie de la base avant mise en service.
