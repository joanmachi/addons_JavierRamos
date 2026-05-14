# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from datetime import date, datetime, time, timedelta

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    def action_update_fecha_entrega(self):
        new_date = False
        for orden in self:
            for linea in orden.order_line:
                if linea.product_template_id and linea.product_template_id.sale_delay:
                    new_date = fields.date.today() + timedelta(days=linea.product_template_id.sale_delay)
                    break
                if new_date:
                    break
            orden.commitment_date = new_date
    
    def action_generate_product_reference(self):
        for orden in self:
            contador = 0
            for linea in orden.order_line:
                if linea.product_template_id:
                    contador = contador + 1
                    if orden.client_order_ref:
                        referencia_cliente = orden.client_order_ref
                    else:
                        referencia_cliente = ''
                    nueva_referencia_producto = '%s%s%s' % (referencia_cliente, orden.name, str(contador).rjust(4, "0") )
                    linea.product_template_id.write({'default_code': nueva_referencia_producto})