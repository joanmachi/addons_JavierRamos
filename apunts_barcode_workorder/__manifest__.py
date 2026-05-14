# -*- coding: utf-8 -*-
{
    'name': "apunts_barcode_workorder",

    'summary': """
        apunts_barcode_workorder
        """,

    'description': """
    """,

    'author': "Apunts Informàtica",
    'website': "http://www.grupapunts.es",

    'depends': ['stock_barcode','stock_barcode_mrp', 'mrp_workorder'],

    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/orden_produccion.xml',
        'wizards/cantidad_wizard_view.xml',
        'reports/fabricacion_report.xml',
    ],
   
    'assets': {
        'web.assets_backend': [
            'apunts_barcode_workorder/static/src/**/*',
        ],
    },
  
    'application': True,
    'installable': True,
}
