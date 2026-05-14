# -*- coding: utf-8 -*-
{
    'name': "javier_ramos_taller_simple",

    'summary': """
        """,

    'description': """
    """,

    'author': "Apunts Informatica",
    'website': "http://www.grupapunts.es",

    'depends': ['mrp_workorder', 'stock', 'purchase_stock', 'product','maintenance', 'mrp_maintenance', 'mrp','quality_mrp_workorder','hr_attendance', 'sale','sale_stock', 'product_secondary_unit','multi_step_wizard','purchase_order_secondary_unit', 'mrp_sale_info'],

    'data': [
        'security/ir.model.access.csv',
        'views/productos_view.xml',
        'views/centro_trabajo_view.xml',
        'views/mrp_bom_view.xml',
        'views/pedidos.xml',
        'views/compras.xml',
        'views/albaran_view.xml',
        'views/fabricacion.xml',
        'wizards/cuestionario_pedido_wizard.xml',
        'report/new_sale_report_inherit.xml',
        'report/albaran_report.xml',
        'report/purchase_order_templates.xml',
        'report/purchase_quotation_templates.xml',
        'report/fabricacion_report.xml',
        'report/paper_format.xml',
        'report/labels.xml',
        'report/etiqueta_reports.xml',
    ],
   
    'assets': {
        'web.assets_backend': [
            'javier_ramos_taller_simple/static/src/**/*',
        ],
    },
  
    'application': True,
    'installable': True,
}
