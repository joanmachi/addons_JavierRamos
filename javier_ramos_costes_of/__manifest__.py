{
    'name': 'JR — Costes consolidados cadena de OFs parciales',
    'version': '18.0.1.0.0',
    'summary': 'Smart button en OFs parciales para ver el coste global de toda la cadena',
    'author': 'Apunts Informàtica',
    'category': 'Manufacturing',
    'license': 'LGPL-3',
    'depends': [
        'apunts_jr_parciales_of',
        'apunts_jr_wip_costes_of',
    ],
    'data': [
        'views/mrp_production_views.xml',
    ],
    'installable': True,
    'application': False,
}
