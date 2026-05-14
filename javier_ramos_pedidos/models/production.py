from odoo import models, fields, api

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # Stored field for dashboard aggregation
    total_value = fields.Monetary(string="Total Value", compute="_compute_total_value", store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.depends('move_raw_ids.product_id', 'move_raw_ids.quantity', 'product_id', 'product_qty')
    def _compute_total_value(self):
        for production in self:
          
            material_cost = sum(
                move.product_id.standard_price *  move.product_uom_qty
                for move in production.move_raw_ids.filtered(lambda m: m.state != 'cancel')
            )

            labor_cost = sum(
                (wo.duration_expected / 60.0) * wo.workcenter_id.costs_hour
                for wo in production.workorder_ids.filtered(lambda w: w.state != 'cancel')
            )

            production.total_value = material_cost + labor_cost