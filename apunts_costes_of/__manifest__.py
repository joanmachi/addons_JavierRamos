{
    'name':     'Apunts — Costes OF (smart button + vista en tiempo real, SOLO CONSULTA)',
    'version':  '18.0.11.0.8',
    'summary':  'Modulo SOLO CONSULTA: smart button "Costes OF" en mrp.production con coste consolidado en tiempo real (material, mano de obra, operacion), trazabilidad backward (PO/proveedor/lote) + forward (SO/cliente/lote/margen incluso si la OF se vincula a SO via campo Studio), asistencias por empleado x dia, comparativa precio venta vs coste real con margen, vista Master Data Costes (consulta) y tooltips informativos en cada KPI. NO MODIFICA datos del Odoo.',
    'author':   'Apunts Informatica',
    'website':  'http://www.grupapunts.es',
    'category': 'Manufacturing',
    'depends':  ['mrp', 'mrp_account', 'purchase_stock', 'sale_management', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/costes_of_lines_views.xml',
        'views/mrp_production_views.xml',
        'views/master_data_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'apunts_costes_of/static/src/css/costes_of.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application':  False,
    'license': 'LGPL-3',
}
