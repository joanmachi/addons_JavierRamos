{
    "name": "Apunts Secondary UoM Pack (Compra + Factura)",
    "summary": "Lectura coherente de UdM secundaria en compras y facturas proveedor",
    "description": """
Apunts Secondary UoM Pack
=========================

Pack que unifica dos correcciones relacionadas con productos que se
manejan internamente en una unidad principal (p.ej. m) pero se compran
o facturan en una unidad secundaria (p.ej. kg).

Funcionalidad
-------------

1. **Factura proveedor — visual**: cuando una línea de factura tiene
   ``secondary_uom_id`` (kg), la columna *UdM* del list y del form
   muestra la unidad secundaria (``kg``) en lugar de la principal del
   producto (``m``). La UdM nativa queda como columna opcional oculta.

2. **Pedido de compra — corrección de cómputo**:

   a. Override de ``purchase.order.line._compute_qty_invoiced`` para que
      cuando la línea de factura llegue en unidad secundaria (kg), el
      ``qty_invoiced`` se calcule en unidad principal (m) usando el
      factor del ``product.secondary.unit``. Antes mostraba "9 m"
      (incorrecto), ahora "0,29 m" (correcto, alineado con
      ``qty_received``).

   b. Campo computed nuevo ``apunts_qty_invoiced_secondary`` que expone
      la cantidad facturada en unidad secundaria (kg).

   c. Reordena las columnas del list de líneas de pedido:
      - ``UdM`` se mueve al lado de ``Cantidad``.
      - Se añade ``Facturado (kg)`` justo a la derecha de ``Facturado``.

Sustituye a los módulos individuales:
``apunts_account_move_secondary_unit`` y
``apunts_purchase_qty_invoiced_fix``.
    """,
    "version": "18.0.2.0.2",
    "category": "Purchases",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": ["account", "purchase", "purchase_order_secondary_unit", "stock"],
    "data": [
        "views/account_move_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
}
