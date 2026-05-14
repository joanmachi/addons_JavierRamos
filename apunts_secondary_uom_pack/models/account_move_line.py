from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    apunts_display_uom_name = fields.Char(
        string="UdM (visible)",
        compute="_compute_apunts_display_uom_name",
        help=(
            "UdM mostrada en facturas. Si la línea tiene UdM secundaria "
            "(ej. kg de un producto medido en m), se muestra la secundaria. "
            "Si no, se muestra la UdM nativa del producto."
        ),
    )

    @api.depends("secondary_uom_id", "product_uom_id")
    def _compute_apunts_display_uom_name(self):
        for line in self:
            if line.secondary_uom_id and line.secondary_uom_id.uom_id:
                line.apunts_display_uom_name = line.secondary_uom_id.uom_id.name
            elif line.product_uom_id:
                line.apunts_display_uom_name = line.product_uom_id.name
            else:
                line.apunts_display_uom_name = False
