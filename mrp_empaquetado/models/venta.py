
from odoo import models, fields, api


class VentaLinea(models.Model):
    _inherit = "sale.order.line"

    cantidad_caja = fields.Integer("Cajas")
    cantidad_en_caja = fields.Float(string="Cantidad en cajas")


    @api.onchange("product_uom_qty")
    def onchange_cantidad(self):
        if self and self.product_uom_qty > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.cantidad_caja = self.product_uom_qty / multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado
    

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super(VentaLinea, self)._prepare_invoice_line(
            **optional_values)
        res.update({
            "cantidad_caja": self.cantidad_caja,
            "cantidad_en_caja": self.cantidad_en_caja,
        })
        return res
    
    @api.onchange("cantidad_caja")
    def onchange_cantidad_caja(self):
        if self and self.cantidad_caja > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.product_uom_qty = self.cantidad_caja * multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado