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


class ReportApuntsPresencia(models.AbstractModel):
    _name = 'report.apunts_jr_gestion_taller.report_apunts_presencia'
    _description = 'Reporte de presencias y ausencias'

    def _tz(self, emp):
        return timezone(emp.tz or self.env.user.tz or 'Europe/Madrid')

    def _fmt_hora(self, dt, emp):
        if not dt:
            return ''
        aware = utc.localize(dt) if dt.tzinfo is None else dt
        return aware.astimezone(self._tz(emp)).strftime('%H:%M:%S')

    @api.model
    def _get_report_values(self, docids, data=None):
        from datetime import datetime as _dt
        lineas = self.env['apunts.historico.presencia'].browse(docids)

        por_emp = {}
        for ln in lineas:
            por_emp.setdefault(ln.employee_id, []).append(ln)

        empleados = []
        fechas = []
        for emp in sorted(por_emp, key=lambda e: e.name or ''):
            regs = sorted(
                por_emp[emp],
                key=lambda r: (r.fecha or _dt.min.date(), r.hora_inicio or _dt.min),
            )
            filas = []
            total_pres = 0.0
            total_aus = 0.0
            for r in regs:
                if r.fecha:
                    fechas.append(r.fecha)
                es_aus = r.tipo == 'ausencia'
                if es_aus:
                    total_aus += r.horas or 0.0
                else:
                    total_pres += r.horas or 0.0
                filas.append({
                    'fecha': r.fecha.strftime('%Y-%m-%d') if r.fecha else '',
                    'dia_semana': DIAS_SEMANA[r.fecha.weekday()] if r.fecha else '',
                    'tipo': 'Ausencia' if es_aus else 'Presencia',
                    'es_ausencia': es_aus,
                    'inicio': '' if es_aus else self._fmt_hora(r.hora_inicio, emp),
                    'fin': '' if es_aus else self._fmt_hora(r.hora_fin, emp),
                    'horas': r.horas or 0.0,
                    'detalle': r.detalle or '',
                })
            empleados.append({
                'nombre': emp.name,
                'departamento': emp.department_id.name or '',
                'filas': filas,
                'total_pres': total_pres,
                'total_aus': total_aus,
                'total': total_pres + total_aus,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'apunts.historico.presencia',
            'docs': lineas,
            'empleados': empleados,
            'fecha_min': min(fechas).strftime('%Y-%m-%d') if fechas else '',
            'fecha_max': max(fechas).strftime('%Y-%m-%d') if fechas else '',
        }
