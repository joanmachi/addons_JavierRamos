{
    "name": "Apunts WIP — Trabajo en Curso",
    "summary": "Módulo independiente de WIP (Work In Progress): valoración de producto en curso + fabricación en curso.",
    "description": """
Apunts WIP — Trabajo en Curso
==============================

Módulo standalone que extrae la funcionalidad WIP que estaba dentro de
`lira_dashboard_contabilidad` (sección Fabricación) a un módulo
independiente. Permite instalar/desinstalar el WIP por separado del
resto del dashboard.

Funcionalidad
-------------

1. **Fabricación en Curso (WIP)** — `apunts.mrp.wip`
   - KPIs: Valoración total WIP, Coste MP, Coste M.O., conteos por estado.
   - Tabla detalle por OF: producto, estado, qty prevista, costes, valor.
   - Filtros: por estado, por categoría, por valoración.

2. **Valoración de Producto en Curso** — `apunts.wip.valuation`
   - KPIs: valor total, coste MP, coste M.O., precio venta, líneas con OF.
   - Tabla detalle por línea de pedido (sale.order.line).
   - Estados cruzados: Estado OF + Estado MP + Estado entrega + Estado factura.
   - Cálculo según las 7 reglas del contable:
     1. Sin MP, sin PO → valor 0
     2. MP pedida (PO conf. sin recibir) → valor 0
     3. MP reservada en almacén → coste MP previsto
     4. OF en progreso/to_close → MP consumida + M.O. acumulada
     5. OF terminada → precio de venta
     6. Entregado → precio de venta
     7. Facturado → precio de venta

Dependencia: requiere `lira_dashboard_contabilidad` instalado para el
widget de impresión y CSS comunes.

Menú raíz propio: **WIP** (en la barra principal de Odoo).
    """,
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": [
        "mrp",
        "sale_management",
        "purchase",
        "stock",
        "lira_dashboard_contabilidad",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/apunts_mrp_wip_views.xml",
        "views/apunts_wip_valuation_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
}
