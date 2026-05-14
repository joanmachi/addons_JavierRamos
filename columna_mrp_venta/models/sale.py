from odoo import models, fields, api

class Venta(models.Model):
    _inherit = 'sale.order'
    
    all_fabricacion = fields.Char(
        string="Albaranes",
        compute="_compute_all_fabricacion",
        store=True,  
    )

    @api.depends('order_line.mrp_production_ids')
    def _compute_all_fabricacion(self):
        for order in self:
            codes = order.order_line.mapped('mrp_production_ids.name')

            unique_codes = set(filter(None, codes))
            order.all_fabricacion = ", ".join(unique_codes) if unique_codes else ""
