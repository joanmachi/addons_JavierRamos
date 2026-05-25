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
    linea_ids = fields.One2many(
        "apunts.fin.jornada.wizard.linea",
        "wizard_id",
        string="OFs abiertas — pon piezas hechas en cada una",
    )
    resumen_html = fields.Html(string="Resumen jornada", compute="_compute_resumen_html")

    def _set_employee_from_pin(self):
        self.ensure_one()
        if not self.pin:
            raise ValidationError(_("Tienes que introducir tu PIN para cerrar la jornada."))
        emp = self.env["hr.employee"].sudo().search([("pin", "=", self.pin)], limit=1)
        if not emp:
            raise ValidationError(_("PIN no reconocido."))
        self.employee_id = emp
        # Crear líneas para cada productividad abierta del operario
        self.linea_ids.unlink()
        productividades_abiertas = self.env["mrp.workcenter.productivity"].search([
            ("employee_id", "=", emp.id),
            ("date_end", "=", False),
        ], order="date_start ASC")
        if productividades_abiertas:
            for p in productividades_abiertas:
                self.env["apunts.fin.jornada.wizard.linea"].create({
                    "wizard_id": self.id,
                    "productivity_id": p.id,
                    "qty_piezas": 0.0,
                })
        return emp

    @api.depends("employee_id", "linea_ids")
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
            if not registros:
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
                    fin_txt = '<strong style="color:#c00">ABIERTO (se cerrará al confirmar)</strong>'
                    seg = (ahora - r.date_start).total_seconds() if r.date_start else 0
                horas = seg / 3600.0
                total_seg += seg
                filas.append(
                    f"<tr><td>{of}</td><td>{wo}</td><td>{ini}</td><td>{fin_txt}</td>"
                    f"<td>{horas:.2f} h</td></tr>"
                )
            total_h = total_seg / 3600.0
            w.resumen_html = (
                f"<p><strong>{w.employee_id.name}</strong> — "
                f"{len(registros)} fichajes hoy · "
                f"<strong>Total: {total_h:.2f} h</strong></p>"
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

    def action_confirmar_fin_jornada(self):
        self.ensure_one()
        if not self.employee_id:
            self._set_employee_from_pin()
        emp = self.employee_id
        if not self.linea_ids:
            if emp.attendance_state == "checked_in":
                emp.sudo()._attendance_action_change()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Jornada cerrada"),
                    "message": _("%s no tenía fichajes abiertos. Check-out de asistencia OK.") % emp.name,
                    "type": "success",
                    "sticky": True,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        ahora = fields.Datetime.now()
        n_cerradas = 0
        wos_a_parar = self.env["mrp.workorder"]
        for ln in self.linea_ids:
            p = ln.productivity_id
            if not p or p.date_end:
                continue
            wo = p.workorder_id
            if wo and ln.qty_piezas:
                try:
                    wo.sudo().write({
                        "qty_ready_to_validate": (wo.qty_ready_to_validate or 0.0) + ln.qty_piezas,
                    })
                except Exception as e:
                    _logger.warning(
                        "Apunts FIN JORNADA: no se pudo sumar qty %s a wo %s: %s",
                        ln.qty_piezas, wo.id, e,
                    )
            if wo and wo.production_id:
                wo.production_id.message_post(body=(
                    "Fin jornada %s — %s piezas reportadas en %s."
                ) % (emp.name, ln.qty_piezas, wo.name))
            if wo:
                wos_a_parar |= wo
            n_cerradas += 1
        for wo in wos_a_parar:
            try:
                wo.stop_employee([emp.id])
            except Exception as e:
                _logger.warning(
                    "Apunts FIN JORNADA: stop_employee falló en wo %s: %s — usando fallback",
                    wo.id, e,
                )
                productivities_emp = wo.time_ids.filtered(
                    lambda t: t.employee_id.id == emp.id and not t.date_end
                )
                productivities_emp.write({"date_end": ahora})
                if emp.id in wo.employee_ids.ids:
                    wo.employee_ids = [(3, emp.id)]
        if emp.attendance_state == "checked_in":
            emp.sudo()._attendance_action_change()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Jornada cerrada"),
                "message": _("%(emp)s — %(n)s fichajes cerrados con piezas reportadas. Check-out OK.") % {
                    "emp": emp.name,
                    "n": n_cerradas,
                },
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class ApuntsFinJornadaWizardLinea(models.TransientModel):
    _name = "apunts.fin.jornada.wizard.linea"
    _description = "Línea OF abierta en wizard fin jornada"

    wizard_id = fields.Many2one(
        "apunts.fin.jornada.wizard", required=True, ondelete="cascade",
    )
    productivity_id = fields.Many2one(
        "mrp.workcenter.productivity", required=True, readonly=True,
    )
    of_name = fields.Char(
        related="productivity_id.workorder_id.production_id.name",
        string="OF", readonly=True,
    )
    ot_name = fields.Char(
        related="productivity_id.workorder_id.name",
        string="OT", readonly=True,
    )
    inicio = fields.Datetime(
        related="productivity_id.date_start", string="Inicio", readonly=True,
    )
    qty_piezas = fields.Float(
        string="Piezas hechas",
        required=True,
        help="Pon 0 si no produjiste piezas en esa OF.",
    )
