from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    apunts_tiene_uom_secundaria = fields.Boolean(
        compute="_compute_apunts_tiene_uom_secundaria",
        help="True si alguna línea del pedido lleva unidad secundaria (kg). "
        "Controla la leyenda de ayuda en el formulario.",
    )

    @api.depends("order_line.secondary_uom_id")
    def _compute_apunts_tiene_uom_secundaria(self):
        for order in self:
            order.apunts_tiene_uom_secundaria = any(
                line.secondary_uom_id for line in order.order_line
            )

    def button_confirm(self):
        res = super().button_confirm()
        # Congelar el factor m/kg vigente en cada línea con unidad
        # secundaria: la recalibración automática posterior ya no puede
        # reinterpretar este pedido. Al recibir se sustituirá por el
        # ratio real medido.
        for line in self.order_line:
            if line.secondary_uom_id and not line.apunts_factor_linea:
                line.apunts_factor_linea = line._get_factor_line()
        return res
