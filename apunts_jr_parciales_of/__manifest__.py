{
    "name": "Apunts JR — Parciales de OF",
    "summary": "Barcode persistente cross-backorder + vista consolidada de OFs parciales (madre + back-orders)",
    "version": "18.0.1.0.3",
    "category": "Manufacturing",
    "author": "Apunts Informàtica",
    "license": "LGPL-3",
    "depends": [
        "mrp",
        "stock_barcode_mrp",
        "apunts_barcode_workorder",
        "apunts_jr_wip_costes_of",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/apunts_jr_costes_cadena_views.xml",
        "views/mrp_production_views.xml",
    ],
    "installable": True,
    "application": False,
}
