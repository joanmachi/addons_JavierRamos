{
    "name": "Apunts JR — Dashboard Dirección",
    "summary": "Panel único de dirección: 10 KPIs con botón directo a la vista de detalle de cada uno",
    "description": """
Panel de Dirección
==================

Una sola pantalla con los 10 KPIs pedidos por dirección. Cada tarjeta
muestra el valor actual y un botón que lleva a la vista ya existente
donde se analiza ese KPI en detalle (dashboard contabilidad, WIP,
carga centros, KPIs de fichaje...).

- Foto semanal automática de todos los KPIs (cron) → "Evolución semanal"
  con gráfico. Los KPIs tipo foto (tesorería, WIP, cartera, cobertura)
  no se pueden reconstruir hacia atrás: la historia empieza al instalar.
- KPI nuevo "Entregas en fecha": albarán de salida validado en o antes
  de la fecha comprometida del pedido de venta (o su fecha de pedido si
  no hay comprometida).
    """,
    "version": "18.0.1.0.0",
    "category": "Reporting",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": [
        "account",
        "sale_stock",
        "mrp",
        "lira_dashboard_contabilidad",
        "apunts_jr_carga_centros",
        "apunts_jr_wip_costes_of",
        "apunts_jr_gestion_taller",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/direccion_resumen_view.xml",
        "views/direccion_snapshot_view.xml",
        "views/stock_picking_views.xml",
        "views/menu.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
