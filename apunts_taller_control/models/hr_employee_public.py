from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    apunts_taller_bloqueado = fields.Boolean(
        related="employee_id.apunts_taller_bloqueado",
        readonly=True,
    )
    apunts_taller_motivo_bloqueo = fields.Char(
        related="employee_id.apunts_taller_motivo_bloqueo",
        readonly=True,
    )
    apunts_taller_fecha_bloqueo = fields.Datetime(
        related="employee_id.apunts_taller_fecha_bloqueo",
        readonly=True,
    )
