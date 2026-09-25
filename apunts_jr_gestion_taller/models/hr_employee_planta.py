"""Quién es personal de planta y cuántas horas de jornada le tocan a cada uno.

La jornada esperada de cada empleado (planta u oficina) sale de SU calendario
laboral de Odoo (40 h/semana, jornada reducida, lo que tenga cada uno),
descontando los festivos del calendario. Las ausencias personales (vacaciones,
bajas) no se descuentan aquí: el KPI las suma aparte como jornada cumplida.
"""
from datetime import date, datetime, time, timedelta

from odoo import fields, models


class HrEmployeePlanta(models.Model):
    _inherit = "hr.employee"

    apunts_planta = fields.Boolean(
        string="Operario de planta",
        help="Trabaja en órdenes del taller. Solo los marcados cuentan en el MACOP "
             "(horas máquina sobre horas de operario en OF). El MACPRE y la jornada "
             "cumplida los mide toda la plantilla, oficina incluida.",
    )

    def _apunts_horas_esperadas_rango(self, ini, fin):
        """Horas de jornada teórica entre dos fechas según el calendario laboral
        del empleado (o el de la empresa), descontando los festivos del calendario.

        Se calcula día a día con las líneas del calendario (no con el helper de
        Odoo, que en esta versión devuelve horas en sábado y domingo cuando el
        rango empieza en fin de semana).

        OJO: se llama «_rango» a propósito. `_apunts_horas_esperadas(dia)` es
        de apunts_taller_control (un solo día) y la usan el fin de jornada y el
        bloqueo diario: no hay que pisarla."""
        self.ensure_one()
        cal = self.resource_calendar_id or self.company_id.resource_calendar_id
        if not cal:
            return 0.0
        ini_d = ini.date() if isinstance(ini, datetime) else ini
        fin_d = fin.date() if isinstance(fin, datetime) else fin
        if not ini_d or not fin_d or fin_d < ini_d:
            return 0.0
        # Festivos: ausencias globales del calendario (sin recurso), en fechas locales
        Leaves = self.env["resource.calendar.leaves"].sudo()
        festivos = set()
        for l in Leaves.search([
            ("resource_id", "=", False),
            ("calendar_id", "in", [cal.id, False]),
            ("date_from", "<=", datetime.combine(fin_d, time.max)),
            ("date_to", ">=", datetime.combine(ini_d, time.min)),
        ]):
            d = max(fields.Date.to_date(l.date_from), ini_d)
            tope = min(fields.Date.to_date(l.date_to), fin_d)
            while d <= tope:
                festivos.add(d)
                d += timedelta(days=1)
        lineas = [a for a in cal.attendance_ids if not a.display_type]
        Att = self.env["resource.calendar.attendance"]
        total = 0.0
        d = ini_d
        while d <= fin_d:
            if d not in festivos:
                semana_tipo = None
                if cal.two_weeks_calendar:
                    try:
                        semana_tipo = str(Att.get_week_type(d))
                    except Exception:
                        semana_tipo = None
                for a in lineas:
                    if int(a.dayofweek) != d.weekday():
                        continue
                    if cal.two_weeks_calendar and a.week_type and semana_tipo and a.week_type != semana_tipo:
                        continue
                    if a.date_from and d < a.date_from:
                        continue
                    if a.date_to and d > a.date_to:
                        continue
                    total += max((a.hour_to or 0.0) - (a.hour_from or 0.0), 0.0)
            d += timedelta(days=1)
        return total
