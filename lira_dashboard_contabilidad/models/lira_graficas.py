from odoo import api, fields, models
from datetime import date
from dateutil.relativedelta import relativedelta

MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
         'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


class LiraGraficasLine(models.TransientModel):
    _name = 'lira.graficas.line'
    _description = 'Línea de datos para gráficas financieras'
    _order = 'mes_orden'

    wizard_id  = fields.Many2one('lira.graficas', ondelete='cascade')
    tipo       = fields.Char()
    mes        = fields.Char(string='Mes',
                             help='Mes del período analizado en formato abreviado')
    mes_orden  = fields.Integer()
    valor      = fields.Float(string='Importe (€)', digits=(16, 2),
                              help='Importe principal del mes')
    valor2     = fields.Float(string='Acumulado (€)', digits=(16, 2),
                              help='Valor acumulado del ejercicio hasta este mes')


class LiraGraficas(models.TransientModel):
    _name = 'lira.graficas'
    _description = 'Gráficas de análisis financiero'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Gráficas Financieras', readonly=True)
    ejercicio = fields.Integer(
        string='Ejercicio',
        default=lambda self: date.today().year,
        help='Año fiscal que se analiza en las gráficas. Cambia el año y pulsa Actualizar.',
    )

    ventas_line_ids = fields.One2many(
        'lira.graficas.line', 'wizard_id',
        domain=[('tipo', '=', 'ventas')],
        string='Ventas',
        help='Evolución mensual de ventas confirmadas (facturas emitidas, sin impuestos)',
    )
    morosos_line_ids = fields.One2many(
        'lira.graficas.line', 'wizard_id',
        domain=[('tipo', '=', 'morosos')],
        string='Clientes morosos',
        help='Importe vencido no cobrado de clientes, agrupado por mes de vencimiento',
    )
    prov_vencidas_line_ids = fields.One2many(
        'lira.graficas.line', 'wizard_id',
        domain=[('tipo', '=', 'prov_vencidas')],
        string='Facturas proveedor vencidas',
        help='Facturas de proveedor vencidas y no pagadas, por mes de vencimiento',
    )
    cashflow_line_ids = fields.One2many(
        'lira.graficas.line', 'wizard_id',
        domain=[('tipo', '=', 'cashflow')],
        string='Cashflow',
        help='Resultado mensual de ingresos menos gastos contabilizados (cuentas 7xx y 6xx)',
    )
    resultado_line_ids = fields.One2many(
        'lira.graficas.line', 'wizard_id',
        domain=[('tipo', '=', 'resultado')],
        string='Resultado mensual',
        help='Beneficio o pérdida mensual: ingresos de explotación menos gastos de explotación',
    )

    def _do_compute(self):
        self.ensure_one()
        cid  = self.env.company.id
        year = self.ejercicio or date.today().year

        today = date.today()
        mes_max = today.month if year == today.year else 12

        ventas_vals = []
        morosos_vals = []
        prov_vals = []
        cashflow_vals = []
        resultado_vals = []
        acumulado = 0.0

        for m in range(1, mes_max + 1):
            ini = date(year, m, 1)
            fin = ini + relativedelta(months=1) - relativedelta(days=1)
            mes_label = f"{m:02d} {MESES[m - 1]}"

            # ── Ventas ────────────────────────────────────────────────────────
            v_moves = self.env['account.move'].search([
                ('company_id', '=', cid),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', ini),
                ('invoice_date', '<=', fin),
            ])
            ventas_vals.append({
                'tipo': 'ventas', 'mes': mes_label, 'mes_orden': m,
                'valor': round(sum(v_moves.mapped('amount_untaxed')), 2),
            })

            # ── Morosos ───────────────────────────────────────────────────────
            mor_moves = self.env['account.move'].search([
                ('company_id', '=', cid),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('invoice_date_due', '>=', ini),
                ('invoice_date_due', '<=', fin),
            ])
            morosos_vals.append({
                'tipo': 'morosos', 'mes': mes_label, 'mes_orden': m,
                'valor': round(sum(mor_moves.mapped('amount_residual')), 2),
            })

            # ── Facturas proveedor vencidas ───────────────────────────────────
            prov_moves = self.env['account.move'].search([
                ('company_id', '=', cid),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('invoice_date_due', '>=', ini),
                ('invoice_date_due', '<=', fin),
            ])
            prov_vals.append({
                'tipo': 'prov_vencidas', 'mes': mes_label, 'mes_orden': m,
                'valor': round(sum(prov_moves.mapped('amount_residual')), 2),
            })

            # ── Cashflow / Resultado ──────────────────────────────────────────
            ing_lines = self.env['account.move.line'].search([
                ('company_id', '=', cid),
                ('account_id.account_type', 'in', ['income', 'income_other']),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', ini), ('date', '<=', fin),
            ])
            gasto_lines = self.env['account.move.line'].search([
                ('company_id', '=', cid),
                ('account_id.account_type', 'in', ['expense', 'expense_direct_cost']),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', ini), ('date', '<=', fin),
            ])
            ingresos = abs(sum(l.debit - l.credit for l in ing_lines))
            gastos   = abs(sum(l.debit - l.credit for l in gasto_lines))
            resultado_mes = round(ingresos - gastos, 2)
            acumulado += resultado_mes

            cashflow_vals.append({
                'tipo': 'cashflow', 'mes': mes_label, 'mes_orden': m,
                'valor': resultado_mes,
            })
            resultado_vals.append({
                'tipo': 'resultado', 'mes': mes_label, 'mes_orden': m,
                'valor': resultado_mes,
                'valor2': round(acumulado, 2),
            })

        self.ventas_line_ids       = [(5,)] + [(0, 0, v) for v in ventas_vals]
        self.morosos_line_ids      = [(5,)] + [(0, 0, v) for v in morosos_vals]
        self.prov_vencidas_line_ids = [(5,)] + [(0, 0, v) for v in prov_vals]
        self.cashflow_line_ids     = [(5,)] + [(0, 0, v) for v in cashflow_vals]
        self.resultado_line_ids    = [(5,)] + [(0, 0, v) for v in resultado_vals]

    @api.onchange('ejercicio')
    def _onchange_ejercicio(self):
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

    @api.model
    def action_open(self):
        rec = self.create({'ejercicio': date.today().year})
        rec._do_compute()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gráficas Financieras',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
