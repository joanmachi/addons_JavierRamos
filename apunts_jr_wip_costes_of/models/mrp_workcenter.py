from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    apunts_amort_hour = fields.Float(
        string="Amortización por hora (€)",
        default=0.0,
        help="Coste de amortización por hora del centro. Sumado al coste por OF.",
    )
