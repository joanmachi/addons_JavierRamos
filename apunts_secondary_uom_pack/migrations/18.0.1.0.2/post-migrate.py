"""Migración post-update v18.0.1.0.2.

Recalcula `qty_invoiced` / `qty_to_invoice` en TODAS las líneas de pedido
de compra con UdM secundaria que estén en estado purchase/done. Pre-fix
arrastraban un residuo de redondeo (factor sec→primaria no exacto) que
dejaba `qty_to_invoice` ligeramente negativo y atrapaba el PO en
"Facturas en espera" aunque estuviese totalmente facturado.

Se ejecuta una sola vez automáticamente al actualizar el módulo.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    pols = env["purchase.order.line"].search([
        ("secondary_uom_id", "!=", False),
        ("order_id.state", "in", ("purchase", "done")),
    ])
    if not pols:
        _logger.info("Apunts secondary_uom_pack: sin POLs con sec_uom para recomputar.")
        return

    _logger.info(
        "Apunts secondary_uom_pack: recomputando qty_invoiced/qty_to_invoice "
        "en %s purchase.order.line con UdM secundaria.",
        len(pols),
    )
    pols.invalidate_recordset(["qty_invoiced", "qty_to_invoice"])
    pols._compute_qty_invoiced()

    pos = pols.order_id
    pos.invalidate_recordset(["invoice_status"])
    # Forzar lectura para disparar el recompute de invoice_status
    for po in pos:
        _ = po.invoice_status

    _logger.info(
        "Apunts secondary_uom_pack: recompute completado en %s POs.", len(pos)
    )
