from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    apunts_fecha_limite = fields.Datetime(
        string="Fecha comprometida",
        compute="_compute_apunts_en_fecha",
        store=True,
        help=(
            "Fecha límite de entrega del pedido de venta origen: la fecha "
            "de entrega comprometida, o la fecha del pedido si no se "
            "comprometió ninguna. Solo en albaranes de salida."
        ),
    )
    apunts_en_fecha = fields.Boolean(
        string="Entregado en fecha",
        compute="_compute_apunts_en_fecha",
        store=True,
        help=(
            "True si el albarán de salida se validó en o antes de la fecha "
            "comprometida del pedido de venta."
        ),
    )

    @api.depends(
        "sale_id.commitment_date",
        "sale_id.date_order",
        "date_done",
        "state",
        "picking_type_id.code",
    )
    def _compute_apunts_en_fecha(self):
        for picking in self:
            limite = False
            if picking.picking_type_id.code == "outgoing" and picking.sale_id:
                limite = (
                    picking.sale_id.commitment_date
                    or picking.sale_id.date_order
                )
            picking.apunts_fecha_limite = limite
            picking.apunts_en_fecha = bool(
                limite
                and picking.state == "done"
                and picking.date_done
                and picking.date_done.date() <= limite.date()
            )
