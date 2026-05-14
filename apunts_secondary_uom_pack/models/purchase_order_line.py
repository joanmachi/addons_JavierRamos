from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    apunts_qty_invoiced_secondary = fields.Float(
        string="Facturado (sec.)",
        compute="_compute_apunts_qty_invoiced_secondary",
        digits="Product Unit of Measure",
        help=(
            "Cantidad facturada expresada en la unidad secundaria de la "
            "línea (p.ej. kg). Solo se rellena si la línea tiene una "
            "unidad secundaria configurada."
        ),
    )

    apunts_uom_short = fields.Char(
        string="UdM",
        compute="_compute_apunts_uom_short",
        help="UdM principal (ej. m) — texto corto para mostrar al lado de la cantidad.",
    )

    apunts_qty_received_secondary = fields.Float(
        string="Recibido (sec.)",
        compute="_compute_apunts_qty_received_secondary",
        store=True,
        digits="Product Unit of Measure",
        help=(
            "Suma de los kg recibidos en los stock.move done de esta línea "
            "(lo que el operario pesó/midió realmente). Independiente de "
            "qty_received (que está en UdM primaria)."
        ),
    )

    @api.depends("move_ids.state", "move_ids.secondary_uom_qty", "move_ids.secondary_uom_id")
    def _compute_apunts_qty_received_secondary(self):
        for line in self:
            if not line.secondary_uom_id:
                line.apunts_qty_received_secondary = 0.0
                continue
            total = 0.0
            for m in line.move_ids:
                if m.state != "done":
                    continue
                if m.secondary_uom_id and m.secondary_uom_id == line.secondary_uom_id:
                    total += m.secondary_uom_qty
            line.apunts_qty_received_secondary = total

    @api.depends("product_uom")
    def _compute_apunts_uom_short(self):
        for line in self:
            line.apunts_uom_short = line.product_uom.name if line.product_uom else False

    @api.depends(
        "invoice_lines.move_id.state",
        "invoice_lines.quantity",
        "invoice_lines.secondary_uom_id",
        "secondary_uom_id",
    )
    def _compute_apunts_qty_invoiced_secondary(self):
        for line in self:
            if not line.secondary_uom_id:
                line.apunts_qty_invoiced_secondary = 0.0
                continue
            total = 0.0
            for aml in line.invoice_lines:
                move = aml.move_id
                if move.state == "cancel" and move.payment_state != "invoicing_legacy":
                    continue
                if not aml.secondary_uom_id or aml.secondary_uom_id != line.secondary_uom_id:
                    continue
                if move.move_type == "in_invoice":
                    total += aml.quantity
                elif move.move_type == "in_refund":
                    total -= aml.quantity
            line.apunts_qty_invoiced_secondary = total

    @api.depends(
        "invoice_lines.move_id.state",
        "invoice_lines.quantity",
        "invoice_lines.product_uom_id",
        "invoice_lines.secondary_uom_id",
        "qty_received",
        "product_qty",
        "secondary_uom_id",
        "secondary_uom_qty",
        "order_id.state",
    )
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()
        for line in self:
            if not line.secondary_uom_id:
                continue
            qty = 0.0
            factor = line._get_factor_line() or 1.0
            for aml in line._get_invoice_lines():
                move = aml.move_id
                if move.state == "cancel" and move.payment_state != "invoicing_legacy":
                    continue
                qty_primary = line._apunts_aml_qty_in_primary(aml, factor)
                if move.move_type == "in_invoice":
                    qty += qty_primary
                elif move.move_type == "in_refund":
                    qty -= qty_primary
            # Redondeo a la precisión del UoM primario: el factor de la UoM
            # secundaria suele ser una fracción no exacta (p.ej. 1/4.9), de modo
            # que `qty_in_sec * factor` arrastra un residuo del orden de 1e-3.
            # Sin este round, `qty_to_invoice = product_qty - qty_invoiced`
            # queda en -0.0016 y `float_is_zero(..., precision_digits=4)` falla.
            rounding = line.product_uom.rounding or 0.01
            line.qty_invoiced = float_round(qty, precision_rounding=rounding)
            if line.order_id.state in ("purchase", "done"):
                if line.product_id.purchase_method == "purchase":
                    delta = line.product_qty - line.qty_invoiced
                else:
                    delta = line.qty_received - line.qty_invoiced
                line.qty_to_invoice = float_round(delta, precision_rounding=rounding)
            else:
                line.qty_to_invoice = 0

    def _prepare_account_move_line(self, move=False):
        """Si el operario rellenó kg reales en la recepción
        (`apunts_qty_received_secondary > 0`), la factura debe llevar
        esos kg reales — no los teóricos del PO line.
        """
        res = super()._prepare_account_move_line(move)
        if self.secondary_uom_id and self.apunts_qty_received_secondary > 0:
            sec_facturados = self.apunts_qty_invoiced_secondary or 0.0
            sec_pendiente = self.apunts_qty_received_secondary - sec_facturados
            if sec_pendiente > 0:
                res["secondary_uom_id"] = self.secondary_uom_id.id
                res["quantity"] = sec_pendiente
        return res

    def _apunts_aml_qty_in_primary(self, aml, factor):
        """Devuelve la cantidad de `aml` expresada en la UoM primaria de la
        línea PO (self). Cubre 3 escenarios:

        1. `aml.secondary_uom_id == self.secondary_uom_id`: la factura declara
           explícitamente la misma sec. → `aml.quantity * factor`.
        2. `aml.secondary_uom_id` distinto: convertir via UoM primaria nativa.
        3. `aml.secondary_uom_id` vacío pero la PO line tiene sec.
           Caso ambiguo (factura importada / manual / no-wizard). Heurística:
           comparar `aml.quantity` contra los candidatos (product_qty y
           secondary_uom_qty del PO line) y elegir la interpretación más cercana.
        """
        self.ensure_one()
        if aml.secondary_uom_id and aml.secondary_uom_id == self.secondary_uom_id:
            return aml.quantity * factor
        if aml.secondary_uom_id and aml.secondary_uom_id != self.secondary_uom_id:
            return aml.product_uom_id._compute_quantity(aml.quantity, self.product_uom)
        # aml sin sec_uom — heurística para resolver ambigüedad
        if (
            self.product_qty
            and self.secondary_uom_qty
            and aml.product_uom_id == self.product_uom
        ):
            dist_primary = abs(aml.quantity - self.product_qty)
            dist_secondary = abs(aml.quantity - self.secondary_uom_qty)
            if dist_secondary < dist_primary:
                # Más cerca de la qty secundaria → la quantity está en sec
                return aml.quantity * factor
        return aml.product_uom_id._compute_quantity(aml.quantity, self.product_uom)
