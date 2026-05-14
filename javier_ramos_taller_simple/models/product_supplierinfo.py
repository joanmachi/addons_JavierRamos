
from odoo import models, fields, api

import logging


_logger = logging.getLogger(__name__)
class SupplierInfo(models.Model):
    _inherit = ["product.supplierinfo", "product.secondary.unit.mixin"]
    _name = 'product.supplierinfo'
    _secondary_unit_fields = {
        "qty_field": "min_qty",
        "uom_field": "product_uom",
    }
    _product_uom_field = "uom_po_id"

    min_qty = fields.Float(
        store=True,
        readonly=False,
        compute="_compute_product_qty",
        copy=True,
        precompute=True,
    )


    @api.depends("secondary_uom_qty", "secondary_uom_id")
    def _compute_product_qty(self):
        self._compute_helper_target_field_qty()

    @api.onchange("product_uom_id")
    def onchange_product_uom_for_secondary(self):
        self._onchange_helper_product_uom_for_secondary()

    @api.onchange("product_id")
    def onchange_product_id(self):
        """If default purchases secondary unit set on product, put on secondary
        quantity 1 for being the default quantity. We override this method,
        that is the one that sets by default 1 on the other quantity with that
        purpose.
        """
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
      


 