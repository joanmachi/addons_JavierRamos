from odoo import models, fields, api


class Scrap(models.Model):
    _inherit = "stock.scrap"

    cantidad_caja = fields.Integer("Cajas")
    cantidad_en_caja = fields.Float(string="Cantidad en cajas")


    @api.onchange("scrap_qty")
    def onchange_cantidad(self):
        if self and self.scrap_qty > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.cantidad_caja = self.scrap_qty / multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado
 

    @api.onchange("cantidad_caja")
    def onchange_cantidad_caja(self):
        if self and self.cantidad_caja > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.scrap_qty = self.cantidad_caja * multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado

