from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    jr_qty_pendiente_entrega = fields.Float(
        string='Saliente',
        compute='_compute_jr_stock_info',
        digits='Product Unit of Measure',
    )
    jr_qty_pendiente_of = fields.Float(
        string='En fabricación',
        compute='_compute_jr_stock_info',
        digits='Product Unit of Measure',
    )
    jr_qty_pendiente_compra = fields.Float(
        string='Compras pdte.',
        compute='_compute_jr_stock_info',
        digits='Product Unit of Measure',
    )

    def _compute_jr_stock_info(self):
        SaleLine = self.env['sale.order.line']
        Production = self.env['mrp.production']
        PurchaseLine = self.env['purchase.order.line']

        for tmpl in self:
            sale_lines = SaleLine.search([
                ('product_template_id', '=', tmpl.id),
                ('qty_to_deliver', '>', 0),
                ('state', '=', 'sale'),
            ])
            tmpl.jr_qty_pendiente_entrega = sum(sale_lines.mapped('qty_to_deliver'))

            mos = Production.search([
                ('product_id.product_tmpl_id', '=', tmpl.id),
                ('state', 'in', ('confirmed', 'progress', 'to_close')),
            ])
            tmpl.jr_qty_pendiente_of = sum(mos.mapped('product_qty'))

            po_lines = PurchaseLine.search([
                ('product_id.product_tmpl_id', '=', tmpl.id),
                ('state', 'in', ('purchase', 'done')),
                ('jr_qty_to_receive', '>', 0),
            ])
            tmpl.jr_qty_pendiente_compra = sum(po_lines.mapped('jr_qty_to_receive'))

    def action_jr_ver_saliente(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'javier_ramos_pedidos.action_jr_sale_line_desglose'
        )
        action['domain'] = [
            ('product_template_id', '=', self.id),
            ('qty_to_deliver', '>', 0),
            ('state', '=', 'sale'),
        ]
        action['context'] = {'search_default_filter_to_deliver': 1}
        return action

    def action_jr_ver_fabricacion(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'OFs en curso',
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'domain': [
                ('product_id.product_tmpl_id', '=', self.id),
                ('state', 'in', ('confirmed', 'progress', 'to_close')),
            ],
        }

    def action_jr_ver_compras(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'javier_ramos_pedidos.action_jr_purchase_line_desglose'
        )
        action['domain'] = [
            ('product_id.product_tmpl_id', '=', self.id),
            ('state', 'in', ('purchase', 'done')),
            ('jr_qty_to_receive', '>', 0),
        ]
        action['context'] = {'search_default_filter_pending': 1}
        return action
