import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ApuntsFinJornadaWizard(models.TransientModel):
    _name = "apunts.fin.jornada.wizard"
    _description = "Wizard fin de jornada operario"

    pin = fields.Char(string="PIN del operario", required=True)
    employee_id = fields.Many2one("hr.employee", string="Operario", readonly=True)
    resumen_html = fields.Html(string="Resumen jornada", compute="_compute_resumen_html")
    aviso_aceptado = fields.Boolean(default=False)
    aviso_jornada_html = fields.Html(string="Aviso jornada", readonly=True)

    def _set_employee_from_pin(self):
        self.ensure_one()
        if not self.pin:
            raise ValidationError(_("Tienes que introducir tu PIN para cerrar la jornada."))
        emp = self.env["hr.employee"].sudo().search([("pin", "=", self.pin)], limit=1)
        if not emp:
            raise ValidationError(_("PIN no reconocido."))
        self.employee_id = emp
        return emp

    @api.depends("employee_id")
    def _compute_resumen_html(self):
        ahora = fields.Datetime.now()
        hoy = date.today()
        for w in self:
            if not w.employee_id:
                w.resumen_html = "<p><em>Introduce tu PIN para ver tu resumen.</em></p>"
                continue
            registros = self.env["mrp.workcenter.productivity"].search([
                ("employee_id", "=", w.employee_id.id),
                ("date_start", ">=", hoy.strftime("%Y-%m-%d 00:00:00")),
            ], order="date_start ASC")
            ausencia_h = w.employee_id._apunts_horas_ausencia(hoy)
            if not registros:
                if ausencia_h:
                    w.resumen_html = (
                        f"<p><strong>{w.employee_id.name}</strong> — "
                        f"sin fichajes de producción hoy · "
                        f"<strong>{ausencia_h:.2f} h de ausencia justificada</strong></p>"
                    )
                else:
                    w.resumen_html = "<p><em>No tienes fichajes hoy.</em></p>"
                continue
            filas = []
            total_seg = 0
            for r in registros:
                of = r.workorder_id.production_id.name or "?"
                wo = r.workorder_id.name or "?"
                ini = fields.Datetime.to_string(r.date_start) if r.date_start else "?"
                if r.date_end:
                    fin_txt = fields.Datetime.to_string(r.date_end)
                    seg = (r.date_end - r.date_start).total_seconds() if r.date_start else 0
                else:
                    fin_txt = '<strong style="color:#c00">ABIERTO — desfíchate antes de cerrar jornada</strong>'
                    seg = (ahora - r.date_start).total_seconds() if r.date_start else 0
                horas = seg / 3600.0
                total_seg += seg
                filas.append(
                    f"<tr><td>{of}</td><td>{wo}</td><td>{ini}</td><td>{fin_txt}</td>"
                    f"<td>{horas:.2f} h</td></tr>"
                )
            total_h = total_seg / 3600.0
            if ausencia_h:
                total_txt = (
                    f"<strong>Total: {total_h:.2f} h fichadas "
                    f"+ {ausencia_h:.2f} h ausencia "
                    f"= {total_h + ausencia_h:.2f} h</strong>"
                )
            else:
                total_txt = f"<strong>Total: {total_h:.2f} h</strong>"
            w.resumen_html = (
                f"<p><strong>{w.employee_id.name}</strong> — "
                f"{len(registros)} fichajes hoy · "
                f"{total_txt}</p>"
                "<table class='table table-sm'>"
                "<thead><tr><th>OF</th><th>OT</th><th>Inicio</th>"
                "<th>Fin</th><th>Duración</th></tr></thead>"
                f"<tbody>{''.join(filas)}</tbody></table>"
            )

    def action_buscar_pin(self):
        self.ensure_one()
        self._set_employee_from_pin()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def _jornada_hoy_insuficiente(self):
        """Si al cerrar ahora la jornada de HOY quedaría por debajo del mínimo
        que activaría el bloqueo (presencia + ausencias < jornada − tolerancia),
        devuelve (presencia, ausencia, esperadas); si no, None.

        Usa la MISMA base que el cron de bloqueo (presencia de hr.attendance +
        ausencias), proyectando la sesión de asistencia aún abierta hasta ahora,
        que es justo lo que el cron evaluará mañana cuando quede cerrada."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("apunts_taller_control.bloqueo_jornada_activo", "1") != "1":
            return None
        emp = self.employee_id
        hoy = fields.Date.context_today(self)
        esperadas = emp._apunts_horas_esperadas(hoy)
        if not esperadas:
            return None  # hoy no es laborable (finde/festivo)
        tol = int(
            ICP.get_param("apunts_taller_control.jornada_tolerancia_min", "10")
        ) / 60.0
        presencia = emp._apunts_horas_presencia(hoy)
        ini, fin = emp._apunts_rango_utc(hoy)
        abierta = self.env["hr.attendance"].search([
            ("employee_id", "=", emp.id),
            ("check_in", ">=", ini), ("check_in", "<=", fin),
            ("check_out", "=", False),
        ], limit=1)
        if abierta:
            presencia += (fields.Datetime.now() - abierta.check_in).total_seconds() / 3600.0
        ausencia = emp._apunts_horas_ausencia(hoy)
        if presencia + ausencia < esperadas - tol:
            return (presencia, ausencia, esperadas)
        return None

    def action_confirmar_fin_jornada(self):
        self.ensure_one()
        if not self.employee_id:
            self._set_employee_from_pin()
        emp = self.employee_id
        productividades_abiertas = self.env["mrp.workcenter.productivity"].search([
            ("employee_id", "=", emp.id),
            ("date_end", "=", False),
        ])
        if productividades_abiertas:
            nombres = []
            for p in productividades_abiertas:
                of = p.workorder_id.production_id.name or "—"
                wo = p.workorder_id.name or "—"
                nombres.append(f"  • {of} — {wo}")
            raise UserError(
                "No puedes cerrar la jornada: tienes OFs con fichaje abierto:\n\n"
                + "\n".join(nombres)
                + "\n\nDesfíchate de cada una escaneando su código de barras y vuelve a intentarlo."
            )
        # Doble confirmación: avisar si la jornada de hoy es insuficiente y el
        # operario quedaría bloqueado mañana. La 1ª pulsación muestra el aviso;
        # la 2ª (aviso_aceptado=True) cierra igualmente.
        if not self.aviso_aceptado:
            datos = self._jornada_hoy_insuficiente()
            if datos:
                presencia, ausencia, esperadas = datos
                total = presencia + ausencia
                aus_txt = (
                    f" + <strong>{ausencia:.2f} h</strong> de ausencia"
                    if ausencia else ""
                )
                aviso = (
                    "<div class='alert alert-danger' role='alert'>"
                    "<h5 class='mb-1'><i class='fa fa-exclamation-triangle me-1'/>"
                    "Jornada por debajo del mínimo</h5>"
                    f"Hoy llevas <strong>{presencia:.2f} h</strong> de presencia{aus_txt} "
                    f"= <strong>{total:.2f} h</strong>, por debajo de las "
                    f"<strong>{esperadas:.2f} h</strong> de tu jornada.<br/>"
                    "Si cierras ahora, mañana quedarás <strong>bloqueado</strong> y "
                    "tendrás que pasar por oficina para volver a fichar.<br/><br/>"
                    "Pulsa de nuevo <strong>«Confirmar y salir»</strong> si aun así "
                    "quieres cerrar la jornada."
                    "</div>"
                )
                self.write({"aviso_aceptado": True, "aviso_jornada_html": aviso})
                return {
                    "type": "ir.actions.act_window",
                    "res_model": self._name,
                    "res_id": self.id,
                    "view_mode": "form",
                    "target": "new",
                    "context": self.env.context,
                }
        if emp.attendance_state == "checked_in":
            emp.sudo()._attendance_action_change()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Jornada cerrada"),
                "message": _("%s — Jornada cerrada correctamente.") % emp.name,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class ApuntsFinJornadaWizardLinea(models.TransientModel):
    _name = "apunts.fin.jornada.wizard.linea"
    _description = "Línea OF (mantenida por compatibilidad)"

    wizard_id = fields.Many2one("apunts.fin.jornada.wizard", ondelete="cascade")
