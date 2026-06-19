from datetime import date, datetime, time, timedelta

from odoo import api, fields, models

MOTIVOS = [
    ('falta_of', 'Falta OF'),
    ('responsabilidad_operario', 'Responsabilidad operario'),
    ('fuerza_mayor', 'Fuerza mayor'),
]


class ApuntsTallerKpi(models.TransientModel):
    _name = 'apunts.taller.kpi'
    _description = 'KPIs de fichaje (taller)'

    fecha_desde = fields.Date(
        string='Desde', required=True,
        default=lambda self: date.today().replace(day=1))
    fecha_hasta = fields.Date(
        string='Hasta', required=True,
        default=lambda self: date.today())

    # KPIs numéricos (también disponibles por si se quieren exportar)
    total_fichajes      = fields.Integer(readonly=True)
    fichajes_corregidos = fields.Integer(readonly=True)
    pct_corregidos      = fields.Float(readonly=True)
    pct_falta_of        = fields.Float(readonly=True)
    pct_resp_operario   = fields.Float(readonly=True)
    pct_fuerza_mayor    = fields.Float(readonly=True)
    pct_cumplimiento    = fields.Float(readonly=True)

    panel_html = fields.Html(string='Panel', readonly=True, sanitize=False)

    # ──────────────────────────────────────────────────────────────────────

    def _rango_utc(self):
        self.ensure_one()
        return (
            datetime.combine(self.fecha_desde, time.min),
            datetime.combine(self.fecha_hasta, time.max),
        )

    @staticmethod
    def _dias_laborables(desde, hasta):
        n, d = 0, desde
        while d <= hasta:
            if d.weekday() < 5:
                n += 1
            d += timedelta(days=1)
        return n

    @staticmethod
    def _tarjeta(valor, etiqueta, color='#1e293b', desc=''):
        return (
            "<div style='flex:1 1 170px;min-width:170px;background:%s;color:#fff;"
            "border-radius:10px;padding:14px;text-align:center;margin:4px;'>"
            "<div style='font-size:1.9rem;font-weight:700;line-height:1;'>%s</div>"
            "<div style='font-size:.9rem;font-weight:600;margin-top:5px;'>%s</div>"
            "<div style='font-size:.72rem;opacity:.8;margin-top:5px;line-height:1.25;'>%s</div>"
            "</div>"
        ) % (color, valor, etiqueta, desc)

    def _calcular(self):
        self.ensure_one()
        Prod = self.env['mrp.workcenter.productivity']
        ini, fin = self._rango_utc()
        dom = [
            ('date_start', '>=', ini), ('date_start', '<=', fin),
            ('employee_id', '!=', False),
        ]
        total = Prod.search_count(dom)
        corregidos = Prod.search_count(dom + [('apunts_modificado_manual', '=', True)])
        por_motivo = {
            k: Prod.search_count(dom + [('apunts_motivo_correccion', '=', k)])
            for k, _ in MOTIVOS
        }
        self.total_fichajes = total
        self.fichajes_corregidos = corregidos
        self.pct_corregidos = (corregidos / total * 100.0) if total else 0.0
        self.pct_falta_of = (por_motivo['falta_of'] / corregidos * 100.0) if corregidos else 0.0
        self.pct_resp_operario = (por_motivo['responsabilidad_operario'] / corregidos * 100.0) if corregidos else 0.0
        self.pct_fuerza_mayor = (por_motivo['fuerza_mayor'] / corregidos * 100.0) if corregidos else 0.0

        # ── Cumplimiento de jornada (agregado: presencia + ausencias / esperadas) ──
        dias_lab = self._dias_laborables(self.fecha_desde, self.fecha_hasta)
        empleados = self.env['hr.employee'].search([
            ('active', '=', True), ('resource_calendar_id', '!=', False),
        ])
        Att = self.env['hr.attendance']
        Leave = self.env['hr.leave']
        total_esp = total_cumpl = 0.0
        filas = []
        for emp in empleados:
            hpd = emp.resource_calendar_id.hours_per_day or 8.0
            esperadas = dias_lab * hpd
            presencia = sum(Att.search([
                ('employee_id', '=', emp.id),
                ('check_in', '>=', ini), ('check_in', '<=', fin),
            ]).mapped('worked_hours'))
            ausencias = sum(Leave.search([
                ('employee_id', '=', emp.id), ('state', '=', 'validate'),
                ('date_from', '<=', fin), ('date_to', '>=', ini),
            ]).mapped('number_of_hours'))
            cumpl = presencia + ausencias
            total_esp += esperadas
            total_cumpl += cumpl
            d_emp = dom + [('employee_id', '=', emp.id)]
            t_emp = Prod.search_count(d_emp)
            c_emp = Prod.search_count(d_emp + [('apunts_modificado_manual', '=', True)])
            if t_emp or cumpl:
                filas.append({
                    'nombre': emp.name,
                    'fichajes': t_emp,
                    'corregidos': c_emp,
                    'pct_corr': (c_emp / t_emp * 100.0) if t_emp else 0.0,
                    'pct_cumpl': (cumpl / esperadas * 100.0) if esperadas else 0.0,
                })
        self.pct_cumplimiento = (total_cumpl / total_esp * 100.0) if total_esp else 0.0

        # ── Panel HTML ──
        cards_corr = (
            self._tarjeta('%d' % total, 'Fichajes', '#334155',
                          'Fichajes en OFs del periodo')
            + self._tarjeta('%.1f%%' % self.pct_corregidos, 'Corregidos', '#b45309',
                            'Corregidos ÷ total fichajes')
            + self._tarjeta('%.0f%%' % self.pct_falta_of, 'Falta OF', '#0e7490',
                            'Motivo Falta OF ÷ corregidos')
            + self._tarjeta('%.0f%%' % self.pct_resp_operario, 'Resp. operario', '#7c3aed',
                            'Motivo Resp. operario ÷ corregidos')
            + self._tarjeta('%.0f%%' % self.pct_fuerza_mayor, 'Fuerza mayor', '#be123c',
                            'Motivo Fuerza mayor ÷ corregidos')
        )
        card_cumpl = self._tarjeta('%.1f%%' % self.pct_cumplimiento, 'Jornada cumplida', '#15803d',
                                   'Presencia + ausencias ÷ jornada esperada (días L-V × h/día)')

        filas.sort(key=lambda f: f['pct_corr'], reverse=True)
        if filas:
            trs = ''.join(
                "<tr><td>%s</td><td class='text-end'>%d</td>"
                "<td class='text-end'>%d</td><td class='text-end'>%.1f%%</td>"
                "<td class='text-end'>%.1f%%</td></tr>" % (
                    f['nombre'], f['fichajes'], f['corregidos'], f['pct_corr'], f['pct_cumpl'])
                for f in filas
            )
            tabla = (
                "<table class='table table-sm table-striped'>"
                "<thead><tr><th>Operario</th><th class='text-end'>Fichajes</th>"
                "<th class='text-end'>Corregidos</th><th class='text-end'>%% corr.</th>"
                "<th class='text-end'>%% jornada</th></tr></thead>"
                "<tbody>%s</tbody></table>" % trs
            )
        else:
            tabla = "<p class='text-muted'>Sin datos en el periodo.</p>"

        self.panel_html = (
            "<h4>Correcciones de fichajes</h4>"
            "<div style='display:flex;flex-wrap:wrap;'>%s</div>"
            "<h4 style='margin-top:16px;'>Cumplimiento de jornada</h4>"
            "<div style='display:flex;flex-wrap:wrap;'>%s</div>"
            "<h4 style='margin-top:16px;'>Detalle por empleado</h4>%s"
        ) % (cards_corr, card_cumpl, tabla)

    def action_calcular(self):
        self.ensure_one()
        self._calcular()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def action_open(self):
        rec = self.create({})
        rec._calcular()
        return {
            'type': 'ir.actions.act_window',
            'name': 'KPIs de fichaje',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
