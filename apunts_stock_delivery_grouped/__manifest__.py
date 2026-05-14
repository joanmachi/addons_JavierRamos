{
    "name": "Apunts Albarán Agrupado por Producto",
    "summary": "Una fila por producto en el PDF del albarán de entrega",
    "description": """
Apunts Albarán Agrupado por Producto
====================================

En el PDF del albarán de entrega (delivery slip nativo Odoo), cuando un
mismo producto se reserva desde varias ubicaciones o lotes, Odoo lo pinta
como filas separadas (una por `stock.move.line`).

Visualmente queda raro al cliente final ver el mismo producto 2-3 veces
con cantidades parciales (ej. 4 + 7) cuando él pidió 11 unidades.

Este módulo agrupa los `stock.move.line` por **producto + UdM** (ignora
description_picking, packaging y ubicación) → el PDF muestra UNA SOLA
fila por producto con la cantidad total.

NO toca lógica de stock — solo el agrupado visual del PDF. Las reservas
internas siguen siendo por ubicación (como debe ser para el operario).
    """,
    "version": "18.0.2.0.1",
    "category": "Inventory",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "views/report_delivery_grouped.xml",
    ],
    "installable": True,
    "application": False,
}
