from odoo import _, fields, models
from odoo.exceptions import ValidationError

# Segundos mínimos entre dos toggles de asistencia del mismo empleado.
# Evita las ráfagas de dobles pulsaciones del PIN que invierten
# entrada/salida y dejan asistencias abiertas o microscópicas.
APUNTS_ANTIRREBOTE_S = 60


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
            if empleado:
                ultima = empleado.last_attendance_id
                referencia = ultima and (ultima.check_out or ultima.check_in)
                if referencia and (
                    fields.Datetime.now() - referencia
                ).total_seconds() < APUNTS_ANTIRREBOTE_S:
                    # No togglear: fichaje repetido en pocos segundos
                    return {
                        "msg": _(
                            "%s: fichaje ignorado, ya fichaste hace un "
                            "momento. Espera un minuto si querías fichar "
                            "de nuevo."
                        )
                        % empleado.name
                    }
        return super().iniciar_taller_pin(pin=pin)
