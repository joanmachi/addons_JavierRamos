{
    'name':    'Lira — Panel Supervisor Fabricación',
    'version': '18.0.1.0.0',
    'summary': 'Vista de supervisión: valida cantidades de planta en 3 clicks',
    'author':  'Apunts Informàtica',
    'website': 'http://www.grupapunts.es',
    'category': 'Manufacturing',
    'application': True,
    'depends': ['mrp', 'mrp_workorder', 'apunts_barcode_workorder'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/lira_validate_wizard_views.xml',
        'views/lira_supervisor_views.xml',
        'views/lira_supervisor_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lira_mfg_supervisor/static/src/css/supervisor.css',
            'lira_mfg_supervisor/static/src/js/supervisor_list.js',
        ],
    },
    'installable': True,
    'license': 'LGPL-3',
}
