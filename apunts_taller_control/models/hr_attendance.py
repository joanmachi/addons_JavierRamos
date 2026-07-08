from odoo import _, models
from odoo.exceptions import ValidationError


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    def iniciar_taller_pin(self, pin=False):
        if pin:
            empleado = self.env["hr.employee"].search([("pin", "=", pin)], limit=1)
            if empleado and empleado.apunts_taller_bloqueado:
                motivo = empleado.apunts_taller_motivo_bloqueo or _("sin motivo registrado")
                raise ValidationError(
                    _(
                        "Empleado %(name)s bloqueado en taller.\n\n"
                        "Motivo: %(motivo)s\n"
                        "Pasa por oficina para que te desbloqueen antes de "
                        "volver a fichar."
                    )
                    % {"name": empleado.name, "motivo": motivo}
                )
        return super().iniciar_taller_pin(pin=pin)
