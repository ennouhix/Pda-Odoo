# -*- coding: utf-8 -*-
{
    'name': "PDA Base",
    'version': '19.0.1.0.0',
    'summary': "Socle backend de l'application PDA (scan de codes-barres)",
    'description': """
PDA Base
========

Socle backend de l'application PDA pour Odoo 19 :

* groupes de sécurité « Opérateur PDA » et « Responsable PDA » ;
* journal des opérations PDA (``pda.log``) ;
* service métier ``pda.service`` (logique de lookup) ;
* endpoints JSON-RPC sécurisés pour la recherche produit par code-barres,
  la liste des emplacements internes et les opérations de stock (réception,
  sortie, transfert, inventaire) ;
* écran PDA « Scanner » en OWL (recherche par code-barres, détail du stock
  par emplacement, opérations de stock, liste des emplacements internes).
""",
    'author': "Odoo PDA",
    'website': "",
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'security/pda_security.xml',
        'security/ir.model.access.csv',
        'views/pda_log_views.xml',
        'views/pda_scanner_action.xml',
        'views/pda_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pda_base/static/src/scanner/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
