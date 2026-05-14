from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    secondary_uom_id = fields.Many2one(
        comodel_name="product.secondary.unit",
        string="UdM secundaria",
        ondelete="restrict",
        copy=False,
    )
    secondary_uom_qty = fields.Float(
        string="Cantidad (UdM sec.)",
        digits="Product Unit of Measure",
        copy=False,
        help=(
            "Cantidad expresada en la UdM secundaria del producto (p.ej. kg). "
            "Independiente de la cantidad principal (p.ej. m): el operario "
            "puede editar las dos por separado al recibir/enviar mercancía."
        ),
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Pre-rellenar SOLO el `secondary_uom_id` (la UdM, NO la cantidad)
        # desde la línea origen (purchase_line_id o sale_line_id) si viene
        # vacío en vals. Razón: queremos que el operario vea la UdM correcta
        # ("kg") en la columna Cant. (sec.), pero la CANTIDAD parte siempre
        # en 0. Así evitamos arrastrar valores teóricos del PO line a moves
        # nuevos (devoluciones, cambios cantidad, transferencias, etc.) que
        # llevarían al operario a creer que ya están rellenos.
        # `secondary_uom_id` puede no existir en sale.order.line si no está
        # instalado `sale_order_secondary_unit`.
        for vals in vals_list:
            if vals.get("secondary_uom_id"):
                continue
            origin_line = None
            if vals.get("purchase_line_id"):
                origin_line = self.env["purchase.order.line"].browse(
                    vals["purchase_line_id"]
                )
            elif vals.get("sale_line_id"):
                origin_line = self.env["sale.order.line"].browse(vals["sale_line_id"])
            if not origin_line or not origin_line.exists():
                continue
            if "secondary_uom_id" not in origin_line._fields:
                continue
            sec_uom = origin_line.secondary_uom_id
            if not sec_uom:
                continue
            vals["secondary_uom_id"] = sec_uom.id
            # Quitar cualquier sec_qty que viniera de un copy() o default
            # — el operario lo rellenará al recepcionar/enviar.
            vals["secondary_uom_qty"] = 0.0
        return super().create(vals_list)


class StockMoveLine(models.Model):
    """Exposición read-only de los campos sec del move padre en la vista
    detallada del picking. La edición se hace sobre `stock.move` directamente
    (un valor por move, no por línea de move).
    """

    _inherit = "stock.move.line"

    secondary_uom_id = fields.Many2one(
        related="move_id.secondary_uom_id",
        string="UdM secundaria",
        readonly=True,
    )
    secondary_uom_qty = fields.Float(
        related="move_id.secondary_uom_qty",
        string="Cantidad (UdM sec.)",
        readonly=False,
    )
