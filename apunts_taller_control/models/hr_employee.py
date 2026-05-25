from odoo import _, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    apunts_taller_bloqueado = fields.Boolean(
        string="Bloqueado en taller",
        default=False,
        tracking=True,
        help=(
            "Cuando está activado, el empleado no puede iniciar nuevos "
            "fichajes desde la vista taller ni hacer toggle de asistencia. "
            "Se activa automáticamente por los crons de control "
            "(>9h continuas en una OF, >5 min sin fichaje activo, etc.). "
            "Solo desbloqueable manualmente desde oficina."
        ),
    )
    apunts_taller_motivo_bloqueo = fields.Char(
        string="Motivo del bloqueo",
        readonly=True,
    )
    apunts_taller_fecha_bloqueo = fields.Datetime(
        string="Fecha del bloqueo",
        readonly=True,
    )

    def action_apunts_desbloquear_taller(self):
        for emp in self:
            emp.write(
                {
                    "apunts_taller_bloqueado": False,
                    "apunts_taller_motivo_bloqueo": False,
                    "apunts_taller_fecha_bloqueo": False,
                }
            )
            emp.message_post(
                body=_(
                    "Empleado desbloqueado para taller por %s."
                ) % self.env.user.name
            )
        return True
