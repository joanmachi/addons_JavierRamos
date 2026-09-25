{
    "name": "Apunts JR — Dashboard Dirección",
    "summary": "Panel de Dirección: reunión semanal en 6 indicadores, histórico semanal de KPIs, cuadros CMI/CMP",
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
    "version": "18.0.3.17.0",
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
        "data/objetivos_data.xml",
        "views/direccion_objetivo_view.xml",
        "views/cmi_semana_view.xml",
        "views/cmp_mes_view.xml",
        "views/cmp_indicador_view.xml",
        "views/cmp_coste_view.xml",
        "views/cmi_hojas_view.xml",
        "views/facturacion_mensual_view.xml",
        "views/direccion_resumen_view.xml",
        "views/direccion_snapshot_view.xml",
        "views/stock_picking_views.xml",
        "views/cartera_views.xml",
        "views/menu.xml",
        "views/kpi_views.xml",
        "views/kpi_consulta_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
