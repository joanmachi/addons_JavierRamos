{
    "name": "Apunts JR — Carga Centros de Trabajo",
    "summary": "Tablero de carga por centro: horas pendientes, fichadas por ventana temporal, órdenes de trabajo abiertas",
    "description": """
Vista resumida de la carga de trabajo de cada centro:
  - Horas pendientes (órdenes de trabajo en estado pending/ready/progress).
  - Horas reales fichadas en los últimos 7, 15 y 30 días.
  - Nº de órdenes de trabajo abiertas.

Pensado para sustituir la vista nativa "Planificación por centros" que es
poco legible. Estilo Resumen (tarjetas) + lista detallada por centro.
    """,
    "version": "18.0.1.2.0",
    "category": "Manufacturing",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": ["mrp", "hr", "mrp_workorder"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/mrp_workcenter_carga_views.xml",
        "views/apunts_carga_resumen_view.xml",
        "views/apunts_carga_snapshot_view.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
}
