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
* endpoints JSON-RPC sécurisés pour la recherche produit par code-barres
  et la liste des emplacements internes.

Ce module ne contient volontairement aucune interface (OWL/frontend).
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
        'views/pda_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
