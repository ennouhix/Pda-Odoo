# -*- coding: utf-8 -*-
{
    'name': "PDA Demo",
    'version': '19.0.1.0.0',
    'summary': "Données de démonstration pour l'application PDA",
    'description': """
PDA Demo
========

Jeu de données prêt pour une démonstration client de l'application PDA :

* quatre emplacements internes scannables (zone, deux rayons, réserve) ;
* six produits réalistes avec codes-barres EAN-13 valides ;
* du stock réparti sur les emplacements ;
* deux comptes de démonstration : opérateur et responsable.

À installer uniquement sur une base de démonstration : les données sont
créées avec ``noupdate="1"`` et le module peut être désinstallé proprement.
""",
    'author': "Odoo PDA",
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'depends': ['pda_base', 'stock'],
    'data': [
        'data/pda_demo_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
