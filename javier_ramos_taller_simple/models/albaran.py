from odoo import models, fields, api
from odoo.tools.float_utils import float_compare, float_is_zero, float_round

class AlbaranLinea(models.Model):
    _inherit = "stock.move"

    fabricacion = fields.Many2one(
        'mrp.production',
        string='Fabricación',
        related="purchase_line_id.fabricacion"
    )
class AlbaranMoveLinea(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_properties(self, move_line=False, move=False):
        res = super(AlbaranMoveLinea,
                    self)._get_aggregated_properties(move_line=move_line, move=move)
        if move:
            res.update({
                "fabricacion": move.fabricacion.name,
            })
        else:
            res.update({
                "fabricacion": self.move_id.fabricacion.name,
            })
        return res




  