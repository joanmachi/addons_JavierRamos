from collections import defaultdict

from pytz import timezone, utc

from odoo import api, models

DIAS_SEMANA = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']


class ReportApuntsAsistencias(models.AbstractModel):
    _name = 'report.apunts_jr_gestion_taller.report_apunts_asistencias'
    _description = 'Reporte diario de registros (asistencias)'

    def _tz(self, emp):
        return timezone(emp.tz or self.env.user.tz or 'Europe/Madrid')

    def _fmt_hora(self, dt, emp):
        if not dt:
            return ''
        aware = utc.localize(dt) if dt.tzinfo is None else dt
        return aware.astimezone(self._tz(emp)).strftime('%H:%M:%S')

    @api.model
    def _get_report_values(self, docids, data=None):
        attendances = self.env['hr.attendance'].browse(docids)

        # Agrupar: empleado -> día -> lista de asistencias
        por_emp = defaultdict(lambda: defaultdict(list))
        for att in attendances:
            if not att.check_in:
                continue
            dia_local = self._fmt_dia(att.check_in, att.employee_id)
            por_emp[att.employee_id][dia_local].append(att)

        empleados = []
        fechas = []
        for emp in sorted(por_emp, key=lambda e: e.name or ''):
            dias_dict = por_emp[emp]
            filas = []
            total = 0.0
            for dia in sorted(dias_dict):
                atts = dias_dict[dia]
                fechas.append(dia)
                check_ins = [a.check_in for a in atts if a.check_in]
                check_outs = [a.check_out for a in atts if a.check_out]
                working = sum(a.worked_hours for a in atts)
                total += working
                filas.append({
                    'fecha': dia.strftime('%Y-%m-%d'),
                    'dia_semana': DIAS_SEMANA[dia.weekday()],
                    'entrada': self._fmt_hora(min(check_ins), emp) if check_ins else '',
                    'salida': self._fmt_hora(max(check_outs), emp) if check_outs else '',
                    'veces': len(check_ins) + len(check_outs),
                    'working': working,
                })
            empleados.append({
                'nombre': emp.name,
                'departamento': emp.department_id.name or '',
                'filas': filas,
                'total': total,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'hr.attendance',
            'docs': attendances,
            'empleados': empleados,
            'fecha_min': min(fechas).strftime('%Y-%m-%d') if fechas else '',
            'fecha_max': max(fechas).strftime('%Y-%m-%d') if fechas else '',
        }

    def _fmt_dia(self, dt, emp):
        aware = utc.localize(dt) if dt.tzinfo is None else dt
        return aware.astimezone(self._tz(emp)).date()
