{
    "name": "Apunts JR — WIP y Coste OF",
    "summary": "Trabajo en curso (WIP) y coste consolidado por orden de fabricación",
    "description": """
Tablero en tiempo real de órdenes de fabricación en curso (WIP) con cálculo
de coste consolidado por OF: materia prima, mano de obra, máquina y
amortización. Una OF entra a WIP cuando se recibe físicamente la materia prima
vinculada y sale cuando se completan todas las piezas.
    """,
    "version": "18.0.1.3.0",
    "category": "Manufacturing",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": ["mrp", "purchase", "stock", "sale_mrp", "apunts_costes_of"],
    "data": [
        "security/ir.model.access.csv",
        "views/mrp_workcenter_views.xml",
        "views/mrp_production_views.xml",
        "views/apunts_wip_resumen_view.xml",
        "views/apunts_costes_of_redesign.xml",
        "views/wizard_buscar_coste.xml",
        "views/menu.xml",
        "views/product_stock_valorado_views.xml",
    ],
    "pre_init_hook": "_pre_init_uninstall_apunts_wip",
    "post_init_hook": "_post_init_recompute_wip",
    "installable": True,
    "application": True,
}
