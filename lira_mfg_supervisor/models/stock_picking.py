from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        res = super()._action_done()
        # Al validar una recepción de compra, verificar si alguna reposición
        # ha quedado totalmente recibida → liberar las piezas pendientes en la PDA.
        pos = self.move_ids.mapped('purchase_line_id.order_id')
        if not pos:
            return res
        Lin = self.env['lira.refabricacion.linea'].sudo()
        lineas = Lin.search([
            ('purchase_order_ids', 'in', pos.ids),
            ('accion', '=', 'reposicion'),
        ])
        wos = lineas.mapped('workorder_id')
        if wos:
            wos._lira_recompute_pdte_recepcion()
        return res
