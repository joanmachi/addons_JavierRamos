from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def write(self, vals):
        res = super().write(vals)
        # Al recibir material de una compra de reposición, recalcular el
        # "pendiente de recepción" de las fases afectadas: las piezas cuyo
        # material ya ha llegado pasan a poder fabricarse ("por hacer").
        if 'qty_received' in vals:
            Lin = self.env['lira.refabricacion.linea'].sudo()
            lineas = Lin.search([
                ('purchase_order_ids', 'in', self.order_id.ids),
                ('accion', '=', 'reposicion'),
            ])
            wos = lineas.workorder_id
            if wos:
                wos._lira_recompute_pdte_recepcion()
        return res
