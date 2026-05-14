
from odoo import models, fields, api
from odoo.exceptions import AccessError, UserError, ValidationError
import logging


_logger = logging.getLogger(__name__)

class CompraLinea(models.Model):
    _inherit = "purchase.order.line"
    fabricacion = fields.Many2one(
        'mrp.production',
        string='Fabricación',
    )

    
    


    def _create_stock_moves(self, picking):
        _logger.info('------------------------ _create_stock_moves')
        res = super(CompraLinea,
                    self)._create_stock_moves(picking=picking)
        for linea in self:
            for linea_albaran in res:
                if linea_albaran.purchase_line_id.id == linea.id:
                    linea_albaran.update({
                        "fabricacion": linea.fabricacion.id,
                    })
        return res
   
    def _prepare_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        if self.secondary_uom_qty > 0:
            cantidad = self.secondary_uom_qty
        else:
            cantidad = self.product_qty
        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            tax_ids=self.taxes_id,
            quantity=cantidad,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id or self.order_id.company_id.currency_id,
            rate=self.order_id.currency_rate,
        )