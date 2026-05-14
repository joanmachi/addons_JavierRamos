from odoo import models, fields, api


class AlbaranLinea(models.Model):
    _inherit = "stock.move"

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
 

    @api.onchange("cantidad_caja")
    def onchange_cantidad_caja(self):
        if self and self.cantidad_caja > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.product_uom_qty = self.cantidad_caja * multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado

    @api.model
    def create(self, vals):
        res = super(AlbaranLinea, self).create(vals)
        if res.sale_line_id:
            res.update({"cantidad_caja": res.sale_line_id.cantidad_caja})
            res.update({"cantidad_en_caja": res.sale_line_id.cantidad_en_caja})
        elif res.purchase_line_id:
            res.update({"cantidad_caja": res.purchase_line_id.cantidad_caja})
            res.update({"cantidad_en_caja": res.purchase_line_id.cantidad_en_caja})
        return res