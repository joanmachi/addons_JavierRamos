from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    jr_qty_to_receive = fields.Float(
        string='Pdte. recibir',
        compute='_compute_jr_qty_to_receive',
        store=True,
        digits='Product Unit of Measure',
    )
    jr_partner_id = fields.Many2one(
        related='order_id.partner_id',
        string='Proveedor',
        store=False,
    )

    @api.depends('product_qty', 'qty_received')
    def _compute_jr_qty_to_receive(self):
        for line in self:
            line.jr_qty_to_receive = max(line.product_qty - line.qty_received, 0.0)
