from odoo import _, api, fields, models


class ApuntsSobreFichajeWizard(models.TransientModel):
    _name = "apunts.sobre.fichaje.wizard"
    _description = "Wizard sobre-fichaje (operario abre 2ª OF mientras tiene otra abierta)"

    barcode_nueva = fields.Char(string="Barcode OF nueva", readonly=True)
    employee_int_id = fields.Integer(string="ID empleado")
    employee_name = fields.Char(string="Operario", readonly=True)
    res_id_int = fields.Integer(string="OF actual del barcode (resId)")

    linea_ids = fields.One2many(
        "apunts.sobre.fichaje.wizard.linea",
        "wizard_id",
        string="OFs en las que ya estás fichado",
    )

    def _ejecutar_resolver(self, accion):
        empleado = {"id": self.employee_int_id, "name": self.employee_name}
        production = self.env["mrp.production"].browse(self.res_id_int)
        return production.apunts_resolver_sobre_fichaje(
            self.barcode_nueva, empleado, accion,
        )

    def action_mantener_doble(self):
        self._ejecutar_resolver("mantener_doble")
        return {"type": "ir.actions.act_window_close"}


class ApuntsSobreFichajeWizardLinea(models.TransientModel):
    _name = "apunts.sobre.fichaje.wizard.linea"
    _description = "Línea OF abierta en wizard sobre-fichaje"

    wizard_id = fields.Many2one(
        "apunts.sobre.fichaje.wizard", required=True, ondelete="cascade",
    )
    productivity_id = fields.Many2one("mrp.workcenter.productivity", readonly=True)
    of_id = fields.Many2one("mrp.production", string="OF", readonly=True)
    ot_name = fields.Char(string="OT", readonly=True)
    inicio = fields.Datetime(string="Fichado desde", readonly=True)

    def action_ir_a_of(self):
        self.ensure_one()
        if not self.of_id:
            return {"type": "ir.actions.act_window_close"}
        return self.of_id.action_open_barcode_client_action()
