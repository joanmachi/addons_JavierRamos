
from odoo import models, fields, api

import logging


_logger = logging.getLogger(__name__)
class MrpBomLine(models.Model):
    _inherit = ["mrp.bom.line", "product.secondary.unit.mixin"]
    _name = 'mrp.bom.line'
    _secondary_unit_fields = {
        "qty_field": "product_qty",
        "uom_field": "product_uom_id",
    }
    _product_uom_field = "uom_po_id"

    product_qty = fields.Float(
        store=True,
        readonly=False,
        compute="_compute_product_qty",
        copy=True,
        precompute=True,
    )
    precio = fields.Float(
        string="Precio"
    )
    total_precio = fields.Float(
        string="Total",
        compute="_compute_total_precio",
    )


    @api.depends("precio", "product_qty")
    def _compute_total_precio(self):
        for linea in self:
            linea.total_precio = linea.product_qty * linea.precio

    @api.depends("secondary_uom_qty", "secondary_uom_id")
    def _compute_product_qty(self):
        self._compute_helper_target_field_qty()

    @api.onchange("product_uom_id")
    def onchange_product_uom_for_secondary(self):
        self._onchange_helper_product_uom_for_secondary()

    @api.onchange("precio")
    def onchange_precio(self):
        if self.product_id and len(self.product_id.seller_ids) and self.product_id.seller_ids[0].price != self.precio:
            self.precio = self.product_id.seller_ids[0].write({
                'price' : self.precio
            })
    @api.onchange("product_id")
    def onchange_product_id(self):
        """If default purchases secondary unit set on product, put on secondary
        quantity 1 for being the default quantity. We override this method,
        that is the one that sets by default 1 on the other quantity with that
        purpose.
        """
        res = super().onchange_product_id()
        if self.product_id and len(self.product_id.seller_ids):
            self.precio = self.product_id.seller_ids[0].price
        # Check to avoid executing onchange unnecessarily,
        # which can sometimes cause tests of other modules to fail
        product_sec_uom = (
            self.product_id.purchase_secondary_uom_id
            or self.product_id.product_tmpl_id.purchase_secondary_uom_id
        )
        if self.secondary_uom_id != product_sec_uom:
            self.secondary_uom_id = product_sec_uom
        if self.secondary_uom_id:
            self.secondary_uom_qty = 1.0
        return res


 