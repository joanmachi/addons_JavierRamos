from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


class LiraSalaryLine(models.TransientModel):
    _name = 'lira.salary.line'
    _description = 'Línea previsión de salarios'

    def action_open_source(self):
        """Abre apuntes contables del grupo 64 (gastos de personal) del mes."""
        self.ensure_one()
        if self.tipo == 'prevision':
            return False
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        try:
            dt_ini = datetime.strptime(self.mes, '%b %Y')
        except Exception:
            try:
                dt_ini = datetime.strptime(self.mes, '%Y-%m')
            except Exception:
                return False
        dt_ini = dt_ini.replace(day=1).date()
        dt_fin = dt_ini + relativedelta(months=1) - relativedelta(days=1)
        return {
            'type': 'ir.actions.act_window',
            'name': f'Apuntes gastos personal — {self.mes}',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('account_id.code', '=like', '64%'),
                ('parent_state', '=', 'posted'),
                ('date', '>=', dt_ini),
                ('date', '<=', dt_fin),
            ],
            'target': 'current',
        }

    wizard_id       = fields.Many2one('lira.salary.forecast', ondelete='cascade')
    mes             = fields.Char('Mes', readonly=True,
        help='Mes al que corresponde la fila')
    tipo            = fields.Selection([
        ('real',      'Real (histórico)'),
        ('prevision', 'Previsión'),
    ], readonly=True,
        help='Real: datos reales de las cuentas contables del grupo 64. Previsión: proyección con el incremento anual configurado')
    salarios_brutos = fields.Float('Salarios brutos (€)', digits=(16, 2),
        help='Importe bruto de salarios del mes. Fuente: account.move.line de cuentas con código 640 (sueldos y salarios)')
    ss_empresa      = fields.Float('Seg. Social empresa (€)', digits=(16, 2),
        help='Coste de Seguridad Social a cargo de la empresa. Se calcula como: salarios brutos × (tasa SS / 100). Para meses históricos se calcula sobre el saldo de la cuenta 640')
    otros           = fields.Float('Otros gastos personal (€)', digits=(16, 2),
        help='Otros gastos de personal distintos del salario. Fuente: account.move.line de cuentas 641, 642, 643 y 649 (indemnizaciones, dietas, seguros, etc.)')
    total           = fields.Float('Total (€)', digits=(16, 2), readonly=True,
        help='Suma de salarios brutos + Seguridad Social empresa + otros gastos de personal del mes')


class LiraSalaryForecast(models.TransientModel):
    _name = 'lira.salary.forecast'
    _description = 'Previsión de gastos de personal'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Previsión de Salarios', readonly=True)

    periodos_hist = fields.Integer('Meses históricos a mostrar', default=6,
        help='Número de meses pasados que se muestran con datos reales de contabilidad. Se leen las cuentas del grupo 64 (gastos de personal)')
    periodos_prev = fields.Integer('Meses de previsión', default=6,
        help='Número de meses futuros que se proyectan usando la media histórica como base y aplicando el incremento anual')
    incremento_pct = fields.Float('Incremento anual (%)', default=3.0,
        help='Porcentaje de subida salarial anual estimado. Se aplica mes a mes con la fórmula: media × (1 + %/100)^(1/12) por mes proyectado')
    tasa_ss        = fields.Float('Tasa Seg. Social empresa (%)', default=29.9,
        help='Porcentaje de Seguridad Social a cargo de la empresa sobre el salario bruto. En España el coste general es aproximadamente 29,9% (contingencias comunes + desempleo + FOGASA + formación)')

    line_ids    = fields.One2many('lira.salary.line', 'wizard_id', string='Evolución')
    tiene_ceros = fields.Boolean(readonly=True)

    total_historico = fields.Float('Total periodo histórico (€)', readonly=True,
        help='Suma del coste total de personal (salarios + SS + otros) de todos los meses históricos mostrados')
    total_prevision = fields.Float('Total previsión (€)', readonly=True,
        help='Suma del coste total de personal previsto para todos los meses futuros proyectados')
    media_mensual   = fields.Float('Media mensual (€)', readonly=True,
        help='Media mensual del coste de personal calculada sobre los meses históricos: total histórico / número de meses')
    media_prevista  = fields.Float('Media mensual prevista (€)', readonly=True,
        help='Media mensual prevista calculada sobre el total de previsión: total previsión / número de meses proyectados')

    def _do_compute(self):
        for rec in self:
            lines_data = []
            today = date.today()

            historico = []
            for i in range(rec.periodos_hist - 1, -1, -1):
                mes_ini = (today - relativedelta(months=i)).replace(day=1)
                mes_fin = mes_ini + relativedelta(months=1) - relativedelta(days=1)

                def bal(prefix):
                    lines = self.env['account.move.line'].search([
                        ('account_id.code', '=like', prefix + '%'),
                        ('move_id.state', '=', 'posted'),
                        ('date', '>=', mes_ini),
                        ('date', '<=', mes_fin),
                        ('company_id', '=', self.env.company.id),
                    ])
                    return sum(l.debit - l.credit for l in lines)

                sal   = bal('640')
                ss    = bal('642')
                otros = bal('641') + bal('643') + bal('649')
                total = sal + ss + otros

                mes_label = mes_ini.strftime('%b %Y')
                historico.append(total)
                lines_data.append({
                    'mes': mes_label, 'tipo': 'real',
                    'salarios_brutos': sal, 'ss_empresa': ss,
                    'otros': otros, 'total': total,
                })

            # Usar mediana de meses con datos reales (total > 0) para ignorar
            # meses con cierre anual acumulado o meses sin nóminas todavía registradas
            hist_validos = sorted(v for v in historico if v > 0)
            if not hist_validos:
                media = 0.0
            elif len(hist_validos) % 2 == 1:
                media = hist_validos[len(hist_validos) // 2]
            else:
                mid = len(hist_validos) // 2
                media = (hist_validos[mid - 1] + hist_validos[mid]) / 2
            factor_mensual = (1 + rec.incremento_pct / 100) ** (1/12)
            total_prev = 0.0
            for i in range(1, rec.periodos_prev + 1):
                mes_fut = today + relativedelta(months=i)
                previsto = media * (factor_mensual ** i)
                sal_prev = previsto / (1 + rec.tasa_ss / 100)
                ss_prev  = sal_prev * rec.tasa_ss / 100
                total_prev += previsto
                lines_data.append({
                    'mes': mes_fut.strftime('%b %Y'), 'tipo': 'prevision',
                    'salarios_brutos': sal_prev, 'ss_empresa': ss_prev,
                    'otros': 0.0, 'total': previsto,
                })

            rec.line_ids = [(5,)] + [(0, 0, d) for d in lines_data]
            rec.tiene_ceros = any(
                d.get('salarios_brutos', 1) == 0
                for d in lines_data if d.get('tipo') == 'real'
            )
            hist_total = sum(d['total'] for d in lines_data if d['tipo'] == 'real')
            rec.total_historico = hist_total
            rec.total_prevision = total_prev
            rec.media_mensual   = round(hist_total / max(rec.periodos_hist, 1), 2)
            rec.media_prevista  = round(total_prev / max(rec.periodos_prev, 1), 2)

    @api.onchange('periodos_hist', 'periodos_prev', 'incremento_pct', 'tasa_ss')
    def _onchange_compute(self):
        self._do_compute()

    def action_refresh(self):
        self._do_compute()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_lines(self):
        self.ensure_one()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_salary_line_list2', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_salary_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Previsión de salarios — detalle completo',
            'res_model': 'lira.salary.line',
            'view_mode': 'list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {'create': False, 'delete': False, 'edit': False},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    @api.model
    def action_open(self):
        rec = self.create({})
        rec._do_compute()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Previsión de salarios',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
