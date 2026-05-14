
{
    "name": "mrp_empaquetado",
    "summary": "Cambia las cantidades de albaranes internos por multiplos de empaquetados",
    "version": "18.0.1.0.0",
    "website": "https://www.apunts.es/",
    "author": "Apunts Informatica ",
    "license": "AGPL-3",
    "installable": True,
    "depends": ["mrp", "sale", "stock", "account", "purchase"],
    "data": [
        "views/scrap_view.xml",
        "views/albaran_view.xml",
        "views/compra_view.xml",
        "views/factura_view.xml",
        "views/venta_view.xml",
        "views/produccion_view.xml",
        "report/albaran_report.xml",
        "report/compra_report.xml",
        "report/factura_report.xml",
        "report/venta_report.xml",
    ],
    
}
