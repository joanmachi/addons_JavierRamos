from odoo import models, fields, api


class FacturaLinea(models.Model):
    _inherit = "account.move.line"

    cantidad_caja = fields.Integer("Cajas")
    cantidad_en_caja = fields.Float(string="Cantidad en cajas")


    @api.onchange("quantity")
    def onchange_cantidad(self):
        if self and self.quantity > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.cantidad_caja = self.quantity / multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado


    @api.onchange("cantidad_caja")
    def onchange_cantidad_caja(self):
        if self and self.cantidad_caja > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.quantity = self.cantidad_caja * multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado