{
    "name": "Apunts SEPA Fecha Cobro Por Línea",
    "summary": "Fecha de cobro SEPA por factura (no global por batch)",
    "description": """
Apunts SEPA Fecha Cobro Por Línea
==================================

En Odoo Enterprise, el batch payment SEPA Direct Debit fuerza una única
`sdd_required_collection_date` para TODAS las facturas del lote — el XML
SEPA resultante lleva un único `ReqdColltnDt`.

Este módulo permite **fecha de cobro por factura** (toma `invoice_date_due`
automáticamente de cada factura del payment) y, al generar el XML, agrupa
los payments por fecha generando **múltiples bloques `PmtInf`** dentro del
mismo fichero SEPA — uno por fecha de cobro distinta. La norma SEPA permite
esto: el banco procesa cada `PmtInf` con su propia fecha.

Funcionalidad
-------------

1. Campo nuevo en `account.payment`: `apunts_sdd_collection_date` (computed
   stored, editable). Por defecto = `invoice_date_due` de la factura
   asociada al pago. Si no hay factura, fallback a `date` del payment.

2. Vista del batch payment: columna "Fecha cobro" editable por línea.

3. Override `account.payment.generate_xml`: agrupa por
   (journal, apunts_sdd_collection_date) en lugar de solo por journal.
   Cada subgrupo → su propio `PmtInf` con su `ReqdColltnDt` correcto.

4. Override `_sdd_xml_gen_payment_group`: usa la fecha del subgrupo
   en vez de la `required_collection_date` global.
    """,
    "version": "18.0.1.0.1",
    "category": "Accounting",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": [
        "account_batch_payment",
        "account_sepa_direct_debit",
    ],
    "data": [
        "views/account_batch_payment_views.xml",
        "views/account_payment_views.xml",
    ],
    "installable": True,
    "application": False,
}
