# -*- coding: utf-8 -*-
{
    'name': "Hanout Demo",
    'version': '19.0.1.0.0',
    'summary': "Comptes et données de test pour une caisse hanout",
    'description': """
Hanout Demo
===========

Jeu de données prêt à l'emploi pour tester la caisse hanout sur une base de
développement :

* deux comptes de test : caissier et gérant hanout ;
* un magasin « Hanout Casablanca » avec son adresse et son téléphone ;
* une caisse Point de Vente en mode hanout simplifié, avec paiement rapide
  en espèces ;
* un petit catalogue d'épicerie (huit articles avec prix et codes-barres) ;
* deux dépenses de caisse d'exemple.

À installer uniquement sur une base de test : les données sont créées en
``noupdate="1"`` et le module peut être désinstallé proprement.
""",
    'author': "Odoo PDA",
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',
    'depends': ['hanout_gest', 'point_of_sale', 'stock'],
    'data': [
        'data/hanout_demo_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
