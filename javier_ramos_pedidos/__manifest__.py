# -*- coding: utf-8 -*-
{
    'name': "javier_ramos_pedidos",

    'summary': """
        """,

    'description': """
    """,

    'author': "Apunts Informatica",
    'website': "http://www.grupapunts.es",
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',

    'depends': ['sale','sale_stock', 'account', 'web', 'mrp'],

    'data': [
        'views/pedidos.xml',
        'views/factura.xml',
        'views/albaran_view.xml',
        'report/albaran_report.xml',
        'report/factura_report.xml',
        'report/venta_report.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'javier_ramos_pedidos/static/src/**/*',
        ],
    },
   

  
    'application': True,
    'installable': True,
}
