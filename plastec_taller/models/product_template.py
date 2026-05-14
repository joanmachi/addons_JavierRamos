
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero



class ProductTemplate(models.Model):
    _inherit = "product.template"

    tipo_palet_id = fields.Many2one(
        comodel_name="plastec_taller.tipo_palet", string="Tipo de Palet"
    )
  