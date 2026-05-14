from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)
class CompraLinea(models.Model):
    _inherit = "purchase.order.line"

    cantidad_caja = fields.Integer("Cajas")
    cantidad_en_caja = fields.Float(string="Cantidad en cajas")


    @api.onchange("product_qty")
    def onchange_cantidad(self):
        if self and self.product_qty > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.cantidad_caja = self.product_qty / multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado
    

    def _prepare_account_move_line(self, move=False):
        self.ensure_one()

        res = super(CompraLinea,
                    self)._prepare_account_move_line(move=move)
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
            self.product_qty = self.cantidad_caja * multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado