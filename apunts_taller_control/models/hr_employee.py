from datetime import datetime, time

from pytz import timezone, utc

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
        self.ensure_one()
        # Detectar caso: ¿tiene fichaje abierto?
        prod_abierta = self.env['mrp.workcenter.productivity'].search([
            ('employee_id', '=', self.id),
            ('date_end', '=', False),
        ], order='date_start DESC', limit=1)

        vals = {
            'employee_id': self.id,
            'motivo_bloqueo': self.apunts_taller_motivo_bloqueo or '',
            'fecha_bloqueo': self.apunts_taller_fecha_bloqueo,
        }

        if prod_abierta:
            # CASO 1: fichado demasiado tiempo → pre-cargar la OF
            vals['production_id'] = prod_abierta.workorder_id.production_id.id or False
        else:
            # CASO 2: inactividad → pre-cargar fechas para el nuevo fichaje
            last_prod = self.env['mrp.workcenter.productivity'].search([
                ('employee_id', '=', self.id),
                ('date_end', '!=', False),
            ], order='date_end DESC', limit=1)
            if last_prod:
                vals['date_start_nuevo'] = last_prod.date_end
            else:
                # Fallback: desde el check_in de asistencia del día
                att = self.env['hr.attendance'].search([
                    ('employee_id', '=', self.id),
                    ('check_out', '=', False),
                ], limit=1)
                if att:
                    vals['date_start_nuevo'] = att.check_in
            vals['date_end_nuevo'] = self.apunts_taller_fecha_bloqueo or fields.Datetime.now()

        wizard = self.env['apunts.corregir.fichaje.wizard'].sudo().create(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Desbloquear operario — %s') % self.name,
            'res_model': 'apunts.corregir.fichaje.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── Helpers de cómputo de jornada (presencia + ausencias) ─────────────────
    # Base compartida por el bloqueo de jornada insuficiente y el resumen de
    # fin de jornada. Criterio acordado con cliente: lo que cuenta es la
    # PRESENCIA (hr.attendance) + las AUSENCIAS aprobadas (hr.leave), igual que
    # vería una inspección de trabajo. El umbral diario sale del calendario del
    # empleado (hours_per_day); como los calendarios son flexibles de 40h y NO
    # definen qué días se trabajan, asumimos L-V (excluyendo festivos globales).

    def _apunts_tz(self):
        """Zona horaria efectiva del empleado para delimitar el día natural."""
        self.ensure_one()
        return (
            self.tz
            or (self.resource_id and self.resource_id.tz)
            or (self.env.company.resource_calendar_id
                and self.env.company.resource_calendar_id.tz)
            or 'UTC'
        )

    def _apunts_rango_utc(self, dia):
        """Devuelve (inicio, fin) del día natural del empleado en UTC naive,
        listos para usar en dominios sobre campos Datetime de Odoo."""
        self.ensure_one()
        tz = timezone(self._apunts_tz())
        ini = tz.localize(datetime.combine(dia, time.min)).astimezone(utc)
        fin = tz.localize(datetime.combine(dia, time.max)).astimezone(utc)
        return ini.replace(tzinfo=None), fin.replace(tzinfo=None)

    def _apunts_es_dia_laborable(self, dia):
        """¿El empleado tenía jornada teórica ese día? Calendario flexible de
        40h sin días fijos ⇒ asumimos L-V y descontamos festivos globales del
        calendario (resource.calendar.leaves sin recurso asignado)."""
        self.ensure_one()
        if dia.weekday() >= 5:  # 5=sábado, 6=domingo
            return False
        ini, fin = self._apunts_rango_utc(dia)
        cal = self.resource_calendar_id
        festivo = self.env['resource.calendar.leaves'].search_count([
            ('resource_id', '=', False),
            ('calendar_id', 'in', [cal.id, False]),
            ('date_from', '<', fin),
            ('date_to', '>', ini),
        ])
        return not festivo

    def _apunts_horas_esperadas(self, dia):
        """Horas teóricas de jornada del empleado ese día (0 si no laborable)."""
        self.ensure_one()
        if not self._apunts_es_dia_laborable(dia):
            return 0.0
        cal = self.resource_calendar_id
        return cal.hours_per_day if cal and cal.hours_per_day else 8.0

    def _apunts_horas_presencia(self, dia):
        """Horas de presencia fichadas (hr.attendance) en el día natural.
        Una asistencia sin check_out cuenta 0 (worked_hours=0): es justo el
        caso 'se olvidó de desfichar' que queremos detectar."""
        self.ensure_one()
        ini, fin = self._apunts_rango_utc(dia)
        atts = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '>=', ini),
            ('check_in', '<=', fin),
        ])
        return sum(atts.mapped('worked_hours'))

    def _apunts_horas_ausencia(self, dia):
        """Horas justificadas por ausencias aprobadas (hr.leave) ese día.
        - Ausencia por horas (request_unit_hours): cuenta number_of_hours.
        - Ausencia por días completos: imputa la jornada teórica del día.
        Se limita a la jornada esperada para no superar el 100% del día."""
        self.ensure_one()
        ini, fin = self._apunts_rango_utc(dia)
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', fin),
            ('date_to', '>=', ini),
        ])
        if not leaves:
            return 0.0
        esperadas = self.resource_calendar_id.hours_per_day or 8.0
        total = 0.0
        for lv in leaves:
            if lv.request_unit_hours:
                total += lv.number_of_hours or 0.0
            else:
                total += esperadas
        return min(total, esperadas) if esperadas else total
