# Hanout Gestion

Gestion d'une boutique de proximité (hanout) sur **Odoo 19 Community**.
Ce module est une couche métier posée sur Point de Vente et Inventaire : la
vente, le catalogue, le stock et la comptabilité restent ceux d'Odoo.

Guide fonctionnel imprimable, toutes fonctions expliquées écran par écran :
[docs/HANOUT_GUIDE.pdf](../../../docs/HANOUT_GUIDE.pdf), régénérable avec
`python3 scripts/build-hanout-guide.py`. Notes de reprise du développement :
[docs/HANOUT_DEV.md](../../../docs/HANOUT_DEV.md).

## Lot 1 — Caisse et clôture journalière (livré)

* **Magasins** (`hanout.shop`) : nom, code unique par société, entrepôt de
  stock, caisses POS rattachées et **séquence de ticket** propre au magasin,
  partagée par toutes ses caisses : les tickets s'appellent
  `HCS/2026/000042` (code du magasin, année, numéro).
* **Cloisonnement par société** : règles d'enregistrement sur les magasins et
  les dépenses ; une caisse et son magasin, une dépense et son magasin,
  doivent appartenir à la même société. Une caisse en mode hanout doit avoir
  un magasin (les caisses Point de Vente classiques restent possibles).
* **Dépenses de caisse** (`hanout.expense`) : libellé, catégorie (achat
  marchandise, transport, électricité, loyer, salaire, entretien, autre),
  montant, magasin et session POS. Le magasin est **obligatoire** (pré-rempli
  quand la société n'en a qu'un).
* **Clôture de session enrichie** : le théorique de caisse d'Odoo est diminué
  des dépenses hanout de la session ; l'écart de comptage affiché tient donc
  compte des sorties d'espèces réelles. Nouvel onglet « Clôture hanout » et
  bouton « Dépenses » sur la session.
* **Groupes** : `Caissier Hanout` (vente, dépenses, clôture de sa session) et
  `Gérant Hanout` (configuration et suppression des dépenses).
* **Mode caisse simplifié** (`pos.config.hanout_simple_mode`, actif par
  défaut) : interface POS épurée pour le caissier — grandes tuiles produits et
  catégories, gros bouton d'encaissement, pavé quantité/prix/remise et actions
  avancées masqués (client, note, remboursement, historique des tickets),
  paiement rapide en espèces. Le bouton **Appliquer le mode hanout simple** de
  la caisse règle tout d'un coup (caisse fermée obligatoire). Le **retour
  client** reste accessible via le bouton « Autres actions » : c'est la seule
  action avancée conservée (pas d'annulation de commande, ni de note client,
  ni de liste de prix).
* **Ticket / facture hanout** : le ticket imprimé affiche en en-tête le nom
  du magasin (majuscules), son adresse et son téléphone, puis le numéro de
  ticket, la date, le caissier, le détail des articles, le total, les
  paiements et la monnaie rendue. En mode simplifié, le ticket est imprimé
  **sans logo société**, sans QR « besoin d'une facture » ni mention Odoo, et
  prend une mise en page hanout : bandeau zellige noir et blanc
  (`static/src/scss/hanout_receipt.scss`), bismillah, nom du magasin en
  majuscules, séparateurs pointillés, **total en bloc inversé** et
  remerciements arabe/français en pied de ticket.

## Lot 2 — Carnet de crédit (livré)

Le carnet s'appuie sur le moyen de paiement natif d'Odoo « Customer Account »
(`pay_later`) : la vente à crédit crée une créance au nom du client dans la
comptabilité, sans journal de dettes maison.

* **Moyen de paiement « Crédit carnet »** : créé sans journal et avec
  l'option « Identify Customer » par le bouton **Appliquer le mode hanout
  simple** de la caisse (si la base possède déjà le moyen de paiement natif
  « Customer Account » avec cette option, il est réutilisé). Sans cette
  option, la créance tomberait sur un compte d'attente anonyme et aucun
  solde client ne serait suivi.
* **Plafond par client** (`res.partner.hanout_credit_limit`, à zéro =
  illimité), solde dû et crédit disponible sur la fiche client.
* **Contrôle du plafond** : un paiement à crédit qui ferait dépasser le
  plafond est refusé, et une vente à crédit sans client aussi. Le contrôle
  tient compte des ventes de la session en cours, pas seulement de la
  comptabilité déjà passée.
* **Solde en temps réel** : solde comptable (créances ouvertes) + **crédit en
  session** (ventes à crédit d'une caisse encore ouverte, comptabilisées
  seulement à la clôture).
* **Hanout > Carnet > Débiteurs** : liste des clients qui doivent encore de
  l'argent, avec le total dû et l'accès direct au règlement.
* **Règlement partiel** : bouton « Règlement carnet » sur la fiche client
  (ou depuis la liste des débiteurs). Le caissier choisit le journal (caisse
  du magasin ou banque) et le montant reçu ; un paiement comptable est
  enregistré puis lettré avec les créances ouvertes, de la plus ancienne à la
  plus récente. Le client peut donc payer une partie seulement.

Limites assumées de ce lot : le crédit d'une session encore ouverte n'existe
pas encore en comptabilité, il n'apparaît donc ni dans la liste des débiteurs
ni dans le solde réglable avant la clôture de la caisse ; le dépassement de
plafond est refusé au moment où le ticket est enregistré, donc après la
validation sur l'écran de caisse, avec le message d'erreur Odoo standard.

## Démarrer la caisse depuis le module hanout

* **Hanout > Vendre** : premier menu du caissier, il ouvre le tableau de bord
  des caisses rattachées à un magasin. Le bouton **Open Register** démarre la
  session de vente (ou la reprend si elle est déjà ouverte). Les sessions et
  les dépenses restent dans **Hanout > Caisse**.
* **Hanout > Magasins > (fiche magasin) > Ouvrir la caisse** : lance
  directement la caisse du magasin. Si le magasin possède plusieurs caisses,
  Odoo propose de choisir laquelle ouvrir.
* Fiche d'une caisse (**Hanout > Configuration > Caisses**) : bouton
  **Ouvrir la caisse**, et bouton **Ouvrir** dans la liste des caisses.

## Installation

```bash
docker compose up -d
docker compose run --rm odoo odoo -d <base> -i hanout_gest --stop-after-init
```

Pour une base de test prête à l'emploi (comptes, magasin, caisse et
catalogue), installer aussi `hanout_demo` :

```bash
docker compose run --rm odoo odoo -d hanout_dev -i hanout_demo --stop-after-init
```

Comptes créés : `hanout.caissier` / `hanout.caissier` (caissier) et
`hanout.gerant` / `hanout.gerant` (gérant).

Puis, dans Odoo : **Hanout > Configuration > Magasins** pour créer le magasin,
et **Point de Vente > Configuration** pour rattacher chaque caisse à son
magasin. Affecter les utilisateurs aux groupes `Caissier Hanout` /
`Gérant Hanout`.

## Utilisation

0. **Préparer la caisse** : Point de Vente > Configuration > ouvrir la caisse,
   choisir le **Magasin hanout**, vérifier qu'un moyen de paiement en espèces
   est présent, puis cliquer **Appliquer le mode hanout simple** : la caisse
   reçoit aussi le moyen de paiement **Crédit carnet**.
1. Le caissier ouvre sa session POS comme d'habitude : l'écran est allégé
   (produits en grandes tuiles, total en gros, bouton « Payer » et paiement
   rapide en espèces).
   Pour le ticket, renseigner dans **Hanout > Configuration > Magasins** le
   téléphone et l'adresse du magasin : ils apparaissent en haut de chaque
   ticket imprimé.
   **Vente à crédit** : sur le ticket, choisir le client puis encaisser avec le
   moyen de paiement **Crédit carnet**. Le plafond se règle sur la fiche du
   client ; **Hanout > Carnet > Débiteurs** liste les dettes, et le bouton
   « Règlement carnet » encaisse un paiement partiel.
2. En cours de journée, **Hanout > Caisse > Dépenses** enregistre les sorties
   d'espèces non marchandes (ou via le bouton « Dépenses » de la session).
3. À la clôture, l'onglet **Clôture hanout** de la session affiche le fond de
   caisse, le total des dépenses, le théorique ajusté et l'écart.

## Tests

```bash
docker compose run --rm odoo odoo -d hanout_dev -u hanout_gest \
  --test-tags /hanout_gest --stop-after-init
```

## Lots suivants

| Lot | Contenu |
| --- | --- |
| 3 | Alertes de rupture en caisse, réappro, inventaire rapide par scan (`pda_base`) |
| 4 | Achats fournisseurs et réception guidée |
| 5 | Tableau de bord gérant : CA, marge, top produits, dettes |
| 6 | Industrialisation : sauvegardes, mises à jour, formation caissier |

### Pourquoi `pay_later` et pas un carnet maison

Vérifié en base avant de développer le lot 2 : une commande payée par un
moyen de paiement `pay_later` est bien soldée, et à la clôture la créance est
portée au **compte client du partenaire** (`121000` dans le plan générique)
quand « Identify Customer » est coché. Sans cette option, la créance tombe sur
le compte d'attente POS sans client : aucun solde ne serait suivi. Le carnet
n'est donc qu'une couche de confort (plafond, écran débiteurs, règlements) sur
un mécanisme comptable natif et fiable.
