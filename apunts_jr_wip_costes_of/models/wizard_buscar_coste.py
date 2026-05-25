from odoo import fields, models


class ApuntsBuscarCosteOf(models.TransientModel):
    _name = "apunts.buscar.coste.of"
    _description = "Buscar OF para ver su coste"

    production_id = fields.Many2one(
        "mrp.production",
        string="Orden de fabricación",
        required=True,
    )

    def action_open_coste(self):
        self.ensure_one()
        return self.production_id.action_apunts_open_costes()
