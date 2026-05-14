from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


class LiraForecastLine(models.TransientModel):
    _name = 'lira.forecast.line'
    _description = 'Línea previsión de liquidez'

    def action_open_source(self):
        """Abre apuntes de ingresos/gastos del mes."""
        self.ensure_one()
        if self.tipo == 'prevision':
            return False  # previsión no tiene origen real
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
            'name': f'Apuntes ingresos/gastos — {self.mes}',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('account_id.account_type', 'in', ['income','income_other','expense','expense_direct_cost']),
                ('parent_state', '=', 'posted'),
                ('date', '>=', dt_ini),
                ('date', '<=', dt_fin),
            ],
            'target': 'current',
        }

    wizard_id       = fields.Many2one('lira.forecast', ondelete='cascade')
    mes             = fields.Char('Mes', readonly=True,
        help='Mes al que corresponde la fila de previsión')
    mes_orden       = fields.Char(readonly=True)
    tipo            = fields.Selection([
        ('historico', 'Histórico'),
        ('prevision', 'Previsión'),
    ], readonly=True,
        help='Histórico: datos reales de contabilidad. Previsión: proyección calculada con el modelo de crecimiento')
    ingresos        = fields.Float('Ingresos (€)', digits=(16, 2), readonly=True,
        help='Ingresos estimados del mes. Fuente: account.move.line con tipo de cuenta income / income_other. Se calcula la media de los meses históricos y se aplica el factor de crecimiento mensual')
    gastos          = fields.Float('Gastos (€)', digits=(16, 2), readonly=True,
        help='Gastos estimados del mes. Fuente: account.move.line con tipo de cuenta expense / expense_direct_cost. Incluye pedidos de compra pendientes de facturar distribuidos en el periodo')
    saldo_mes       = fields.Float('Saldo mes (€)', digits=(16, 2), readonly=True,
        help='Ingresos menos gastos del mes. Un valor negativo indica que ese mes se prevé un déficit de caja')
    saldo_acumulado = fields.Float('Saldo acum. (€)', digits=(16, 2), readonly=True,
        help='Suma acumulada de todos los saldos mensuales desde el inicio del periodo proyectado. Muestra la evolución del saldo total de caja')


class LiraBankLine(models.TransientModel):
    _name = 'lira.bank.line'
    _description = 'Saldo por cuenta bancaria/caja'

    wizard_id      = fields.Many2one('lira.forecast', ondelete='cascade')
    nombre_cuenta  = fields.Char('Cuenta', readonly=True)
    codigo_cuenta  = fields.Char('Código', readonly=True)
    saldo          = fields.Float('Saldo (€)', digits=(16, 2), readonly=True)


class LiraForecast(models.TransientModel):
    _name = 'lira.forecast'
    _description = 'Previsión de liquidez mensual'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Previsión de Liquidez', readonly=True)

    meses_hist     = fields.Integer('Meses históricos', default=3,
        help='Número de meses pasados que se usan para calcular el promedio de ingresos y gastos. Cuantos más meses, más estable es la base de cálculo')
    meses_prev     = fields.Integer('Meses de previsión', default=6,
        help='Número de meses futuros que se proyectan. El modelo aplica el porcentaje de crecimiento anual mes a mes')
    incremento_pct = fields.Float('Incremento anual (%)', default=3.0,
        help='Porcentaje de crecimiento anual esperado. Se convierte a factor mensual: (1 + %/100)^(1/12). Un 3% anual equivale a un 0,25% mensual aproximadamente')

    line_ids         = fields.One2many('lira.forecast.line', 'wizard_id', string='Evolución')
    banco_ids        = fields.One2many('lira.bank.line', 'wizard_id', string='Saldo por cuenta')
    tiene_ceros      = fields.Boolean(readonly=True)
    total_ingresos   = fields.Float('Total ingresos previstos (€)', readonly=True,
        help='Suma de todos los ingresos mensuales previstos en el periodo proyectado')
    total_gastos     = fields.Float('Total gastos previstos (€)', readonly=True,
        help='Suma de todos los gastos mensuales previstos en el periodo proyectado. Incluye la distribución de facturas de proveedor pendientes de pago')
    saldo_total      = fields.Float('Saldo neto total (€)', readonly=True,
        help='Ingresos totales previstos menos gastos totales previstos del periodo completo')
    saldo_minimo     = fields.Float('Saldo mínimo mensual (€)', readonly=True,
        help='El saldo más bajo entre todos los meses previstos. Un valor muy negativo indica riesgo de tensión de tesorería ese mes')
    mes_critico      = fields.Char('Mes más crítico', readonly=True,
        help='Mes con el saldo mensual más negativo del periodo proyectado. Si todos los meses son positivos muestra "—"')
    meses_negativos  = fields.Integer('Meses con saldo negativo', readonly=True,
        help='Número de meses en que los gastos previstos superan a los ingresos previstos. Sirve como indicador de riesgo de liquidez')
    saldo_bancos     = fields.Float('Saldo total bancos (€)', readonly=True, digits=(16, 2),
        help='Saldo real total disponible hoy en todas las cuentas bancarias y de caja')

    def _do_compute(self):
        for rec in self:
            today = date.today()
            n_hist = max(rec.meses_hist, 1)
            n_prev = max(rec.meses_prev, 1)
            cid = self.env.company.id

            # ── Saldo por cuenta bancaria/caja ────────────────────────────────
            accounts = self.env['account.account'].search([
                ('account_type', '=', 'asset_cash'),
                ('company_ids', 'in', [cid]),
            ])
            banco_data = []
            total_bancos = 0.0
            for acc in accounts:
                lines = self.env['account.move.line'].search([
                    ('account_id', '=', acc.id),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', cid),
                ])
                saldo = round(sum(l.debit - l.credit for l in lines), 2)
                total_bancos += saldo
                if abs(saldo) > 0.001:
                    banco_data.append({
                        'nombre_cuenta': acc.name,
                        'codigo_cuenta': acc.code,
                        'saldo': saldo,
                    })
            rec.banco_ids = [(5,)] + [(0, 0, d) for d in banco_data]
            rec.saldo_bancos = round(total_bancos, 2)

            def avg_monthly(account_types):
                totals = []
                for i in range(n_hist):
                    ini = (today - relativedelta(months=i)).replace(day=1)
                    fin = ini + relativedelta(months=1) - relativedelta(days=1)
                    lines = self.env['account.move.line'].search([
                        ('account_id.account_type', 'in', account_types),
                        ('move_id.state', '=', 'posted'),
                        ('date', '>=', ini), ('date', '<=', fin),
                        ('company_id', '=', self.env.company.id),
                    ])
                    totals.append(abs(sum(l.debit - l.credit for l in lines)))
                return sum(totals) / len(totals) if totals else 0.0

            ing_medio   = avg_monthly(['income', 'income_other'])
            gasto_medio = avg_monthly(['expense', 'expense_direct_cost'])

            so_pending = self.env['sale.order'].search([
                ('state', 'in', ['sale', 'done']),
                ('invoice_status', '=', 'to invoice'),
                ('company_id', '=', self.env.company.id),
            ])
            ing_extra = sum(o.amount_untaxed for o in so_pending) / n_prev

            bills_pending = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('company_id', '=', self.env.company.id),
            ])
            gasto_extra = sum(b.amount_residual for b in bills_pending) / n_prev

            factor_mensual = (1 + rec.incremento_pct / 100) ** (1 / 12)

            lines_data = []
            saldo_acum = 0.0

            for i in range(n_prev):
                mes_d = today + relativedelta(months=i)
                label = mes_d.strftime('%b %Y')
                orden = mes_d.strftime('%Y-%m')
                factor = factor_mensual ** i

                ingresos = round((ing_medio + ing_extra) * factor, 2)
                gastos   = round((gasto_medio + gasto_extra) * factor, 2)
                saldo    = round(ingresos - gastos, 2)
                saldo_acum = round(saldo_acum + saldo, 2)

                lines_data.append({
                    'mes': label,
                    'mes_orden': orden,
                    'tipo': 'historico' if i == 0 else 'prevision',
                    'ingresos': ingresos,
                    'gastos': gastos,
                    'saldo_mes': saldo,
                    'saldo_acumulado': saldo_acum,
                })

            rec.line_ids = [(5,)] + [(0, 0, d) for d in lines_data]
            rec.tiene_ceros = any(
                d.get('ingresos', 1) == 0 or d.get('gastos', 1) == 0
                for d in lines_data
            )

            prev_lines = lines_data
            rec.total_ingresos  = round(sum(d['ingresos'] for d in prev_lines), 2)
            rec.total_gastos    = round(sum(d['gastos'] for d in prev_lines), 2)
            rec.saldo_total     = round(sum(d['saldo_mes'] for d in prev_lines), 2)
            rec.meses_negativos = sum(1 for d in prev_lines if d['saldo_mes'] < 0)

            if prev_lines:
                min_line = min(prev_lines, key=lambda x: x['saldo_mes'])
                rec.saldo_minimo = min_line['saldo_mes']
                rec.mes_critico  = min_line['mes'] if min_line['saldo_mes'] < 0 else '—'
            else:
                rec.saldo_minimo = 0.0
                rec.mes_critico  = '—'

    @api.onchange('meses_hist', 'meses_prev', 'incremento_pct')
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
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_forecast_line_list2', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_forecast_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Previsión de liquidez — detalle completo',
            'res_model': 'lira.forecast.line',
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
            'name': 'Previsión de Liquidez',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
