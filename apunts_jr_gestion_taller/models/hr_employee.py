from datetime import date, timedelta

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    apunts_horas_hoy = fields.Float(
        string='Horas hoy',
        compute='_compute_apunts_horas_resumen',
        help='Suma de horas fichadas en mrp.workcenter.productivity hoy.',
    )
    apunts_horas_semana = fields.Float(
        string='Horas semana',
        compute='_compute_apunts_horas_resumen',
        help='Suma de horas fichadas desde el lunes de esta semana hasta hoy (incluido).',
    )
    apunts_fichaje_activo_count = fields.Integer(
        string='Fichajes abiertos',
        compute='_compute_apunts_horas_resumen',
        help='Número de productivities abiertas (date_end IS NULL) ahora mismo.',
    )

    apunts_productivity_actual_id = fields.Many2one(
        'mrp.workcenter.productivity',
        string='Fichaje actual',
        compute='_compute_apunts_actual',
        help='Productivity abierta más reciente del empleado (date_end IS NULL).',
    )
    apunts_of_actual_id = fields.Many2one(
        related='apunts_productivity_actual_id.workorder_id.production_id',
        string='OF actual',
    )
    apunts_ot_actual_id = fields.Many2one(
        related='apunts_productivity_actual_id.workorder_id',
        string='OT actual',
    )
    apunts_centro_actual_id = fields.Many2one(
        related='apunts_productivity_actual_id.workcenter_id',
        string='Centro actual',
    )
    apunts_fichado_desde = fields.Datetime(
        related='apunts_productivity_actual_id.date_start',
        string='Fichado desde',
    )
    apunts_llevan_h = fields.Float(
        string='Llevan (h)',
        compute='_compute_apunts_llevan_h',
        help='Horas desde el inicio del fichaje actual.',
    )
    apunts_of_actual_num = fields.Char(
        string='OF #',
        compute='_compute_apunts_of_actual_num',
        help='Solo el número final de la OF (sin FAB/MO/).',
    )
    apunts_ot_actual_name = fields.Char(
        string='OT',
        related='apunts_ot_actual_id.name',
        help='Nombre corto de la OT (solo la operación, sin FAB/MO/).',
    )
    apunts_ofs_actuales_summary = fields.Html(
        string='OFs actuales',
        compute='_compute_apunts_ofs_actuales_summary',
        sanitize=False,
        help='Lista de TODAS las OFs en las que el empleado está fichado ahora mismo, una por línea.',
    )

    def _compute_apunts_ofs_actuales_summary(self):
        Productivity = self.env['mrp.workcenter.productivity']
        for emp in self:
            registros = Productivity.search([
                ('employee_id', '=', emp.id),
                ('date_end', '=', False),
            ])
            if not registros:
                emp.apunts_ofs_actuales_summary = False
                continue
            lineas = []
            for r in registros:
                of = r.workorder_id.production_id.name or '?'
                of_corto = of.split('/')[-1] if of else '?'
                ot = r.workorder_id.name or '?'
                lineas.append(f'<div>{of_corto} ({ot})</div>')
            emp.apunts_ofs_actuales_summary = ''.join(lineas)

    def _compute_apunts_actual(self):
        Productivity = self.env['mrp.workcenter.productivity']
        for emp in self:
            emp.apunts_productivity_actual_id = Productivity.search(
                [('employee_id', '=', emp.id), ('date_end', '=', False)],
                order='date_start DESC',
                limit=1,
            )

    def _compute_apunts_of_actual_num(self):
        for emp in self:
            of = emp.apunts_of_actual_id
            if of and of.name:
                emp.apunts_of_actual_num = of.name.split('/')[-1]
            else:
                emp.apunts_of_actual_num = False

    def _compute_apunts_llevan_h(self):
        ahora = fields.Datetime.now()
        for emp in self:
            ini = emp.apunts_fichado_desde
            if ini:
                emp.apunts_llevan_h = (ahora - ini).total_seconds() / 3600.0
            else:
                emp.apunts_llevan_h = 0.0

    def action_apunts_ver_of_actual(self):
        self.ensure_one()
        if not self.apunts_of_actual_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.apunts_of_actual_id.name,
            'res_model': 'mrp.production',
            'res_id': self.apunts_of_actual_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _compute_apunts_horas_resumen(self):
        hoy = date.today()
        ini_semana = hoy - timedelta(days=hoy.weekday())
        ahora = fields.Datetime.now()
        Productivity = self.env['mrp.workcenter.productivity']
        for emp in self:
            todos = Productivity.search([('employee_id', '=', emp.id)])
            horas_hoy = 0.0
            horas_semana = 0.0
            n_abiertos = 0
            for p in todos:
                if not p.date_start:
                    continue
                fin = p.date_end or ahora
                delta_h = (fin - p.date_start).total_seconds() / 3600.0
                if p.date_start.date() == hoy:
                    horas_hoy += delta_h
                if p.date_start.date() >= ini_semana:
                    horas_semana += delta_h
                if not p.date_end:
                    n_abiertos += 1
            emp.apunts_horas_hoy = horas_hoy
            emp.apunts_horas_semana = horas_semana
            emp.apunts_fichaje_activo_count = n_abiertos
