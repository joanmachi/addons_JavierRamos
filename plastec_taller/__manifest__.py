# -*- coding: utf-8 -*-
{
    'name': "plastec_taller",

    'summary': """
        """,

    'description': """
    """,

    'author': "Apunts Informatica",
    'website': "http://www.grupapunts.es",

    'depends': ['mrp_workorder', 'stock'],

    'data': [
        'security/ir.model.access.csv',
        'views/tipos_palets_views.xml',
        'views/acciones.xml',
    ],
   
    'assets': {
        'web.assets_backend': [
            'plastec_taller/static/src/**/*',
        ],
    },
  
    'application': True,
    'installable': True,
}
