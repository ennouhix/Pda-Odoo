# -*- coding: utf-8 -*-
{
    'name': "Hanout Gestion",
    'version': '19.0.1.2.0',
    'summary': "Gestion de boutique : magasin, caisse et clôture journalière",
    'description': """
Hanout Gestion
==============

Gestion d'une boutique de proximité (hanout) sur Odoo 19 :

* magasins ``hanout.shop`` rattachés à un entrepôt et à une ou plusieurs
  caisses Point de Vente ;
* dépenses de caisse ``hanout.expense`` (achat marchandise, transport,
  électricité, salaire, etc.) saisies en cours de journée ;
* clôture de session POS enrichie : le théorique de caisse est diminué des
  dépenses du jour, l'écart de comptage affiché tient donc compte des sorties
  d'espèces réelles ;
* carnet de crédit client : plafond, solde en temps réel, écran des
  débiteurs et règlements partiels lettrés sur les créances ;
* groupes « Caissier Hanout » et « Gérant Hanout ».

La vente, le catalogue, le stock et la comptabilité restent ceux d'Odoo :
ce module ne duplique aucune logique existante. Les lots suivants couvriront
les alertes de rupture et le tableau de bord.
""",
    'author': "Odoo PDA",
    'website': "",
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'stock'],
    'data': [
        'security/hanout_security.xml',
        'security/ir.model.access.csv',
        'security/hanout_rules.xml',
        'views/hanout_shop_views.xml',
        'views/res_partner_views.xml',
        'views/hanout_expense_views.xml',
        'views/pos_config_views.xml',
        'views/pos_session_views.xml',
        'views/hanout_menus.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'hanout_gest/static/src/xml/hanout_receipt.xml',
            'hanout_gest/static/src/xml/hanout_control_buttons.xml',
            'hanout_gest/static/src/js/hanout_pos.js',
            'hanout_gest/static/src/scss/hanout_pos.scss',
            'hanout_gest/static/src/scss/hanout_receipt.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
