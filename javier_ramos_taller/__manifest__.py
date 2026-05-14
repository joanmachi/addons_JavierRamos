# -*- coding: utf-8 -*-
{
    'name': "javier_ramos_taller",

    'summary': """
        """,

    'description': """
    """,

    'author': "Apunts Informatica",
    'website': "http://www.grupapunts.es",

    'depends': ['mrp_workorder', 'stock', 'maintenance', 'mrp_maintenance', 'mrp','quality_mrp_workorder','hr_attendance'],

    'data': [
    ],
   
    'assets': {
        'web.assets_backend': [
            'javier_ramos_taller/static/src/**/*',
        ],
    },
  
    'application': True,
    'installable': True,
}
