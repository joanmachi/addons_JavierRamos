from odoo import models, fields, api
from datetime import date


# ═══════════════════════════════════════════════════════════════════════════
# Cuentas marcadas por el contable como COSTES VARIABLES
# El resto de cuentas 6xx se consideran FIJOS
# ═══════════════════════════════════════════════════════════════════════════
CUENTAS_VARIABLES = [
    '60010005',
    '601007',
    '6070002',
    '6070003',
    '600017',
    '6000018',
    '62800001',
]


class LiraPnlLine(models.Model):
    _name = 'lira.pnl.line'
    _description = 'Línea P&G por cuenta'
    _order = 'bloque, saldo desc'

    user_id           = fields.Many2one('res.users', ondelete='cascade', index=True)
    bloque            = fields.Selection([
        ('ingresos',  'Ingresos'),
        ('variables', 'Costes variables'),
        ('fijos',     'Costes fijos'),
    ], string='Bloque', index=True)
    account_id        = fields.Many2one('account.account', string='Cuenta', index=True)
    codigo_cuenta     = fields.Char('Código cuenta', index=True)
    nombre_cuenta     = fields.Char('Nombre cuenta')
    saldo             = fields.Float('Saldo (€)', digits=(16, 2))
    pct_sobre_bloque  = fields.Float('% sobre bloque', digits=(16, 2))
    pct_sobre_ingresos = fields.Float('% sobre ingresos', digits=(16, 2))
    date_from         = fields.Date('Desde')
    date_to           = fields.Date('Hasta')

    def action_open_source(self):
        """Abre los apuntes contables de esta cuenta en el periodo analizado."""
        self.ensure_one()
        if not self.account_id:
            return False
        domain = [
            ('account_id', '=', self.account_id.id),
            ('parent_state', '=', 'posted'),
        ]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        return {
            'type': 'ir.actions.act_window',
            'name': f'Apuntes {self.codigo_cuenta} — {self.nombre_cuenta}',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }


class LiraPnlPeriod(models.TransientModel):
    _name = 'lira.pnl.period'
    _description = 'P&G por periodos con desglose fijos/variables'
    _rec_name = 'display_title'

    display_title = fields.Char(default='P&G por Periodos', readonly=True)

    date_from = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to   = fields.Date('Hasta', default=fields.Date.today)

    # KPIs
    total_ingresos  = fields.Float('Total ingresos (€)',  readonly=True)
    total_variables = fields.Float('Costes variables (€)', readonly=True)
    total_fijos     = fields.Float('Costes fijos (€)',     readonly=True)
    margen_bruto    = fields.Float('Margen bruto (€)',     readonly=True,
        help='Ingresos − Costes variables')
    margen_bruto_pct = fields.Float('Margen bruto (%)',    readonly=True,
        help='(Ingresos − Variables) / Ingresos × 100')
    resultado        = fields.Float('Resultado (€)',       readonly=True,
        help='Ingresos − Variables − Fijos')
    resultado_pct    = fields.Float('Resultado (%)',       readonly=True,
        help='Resultado / Ingresos × 100')

    num_ctas_ingresos  = fields.Integer('Cuentas de ingresos',  readonly=True)
    num_ctas_variables = fields.Integer('Cuentas variables',    readonly=True)
    num_ctas_fijos     = fields.Integer('Cuentas fijas',        readonly=True)

    # ────────────────────────────────────────────────────────────────────────
    def _build_data(self):
        df = self.date_from or date.today().replace(month=1, day=1)
        dt = self.date_to   or date.today()
        cid = self.env.company.id

        # Apuntes contabilizados del periodo
        AML = self.env['account.move.line']
        aml_lines = AML.search([
            ('parent_state', '=', 'posted'),
            ('date', '>=', df),
            ('date', '<=', dt),
            ('company_id', '=', cid),
            ('account_id', '!=', False),
        ])

        # Agregar por cuenta: saldo según tipo
        # Ingresos (7xx): credit - debit (positivo = ingreso)
        # Gastos (6xx): debit - credit (positivo = gasto)
        buckets = {}  # account_id -> {'acc': account, 'saldo': float, 'bloque': str}
        # Leer códigos variables desde la configuración (UI) con fallback a la constante
        vars_set = set(self.env['lira.variable.account'].get_variable_codes())
        for ln in aml_lines:
            acc = ln.account_id
            code = acc.code or ''
            # Clasificación
            if code.startswith('7'):
                bloque = 'ingresos'
                delta = (ln.credit or 0.0) - (ln.debit or 0.0)
            elif code.startswith('6'):
                bloque = 'variables' if code in vars_set else 'fijos'
                delta = (ln.debit or 0.0) - (ln.credit or 0.0)
            else:
                continue  # ignoramos balance (1xx,2xx,3xx,4xx,5xx)
            key = acc.id
            if key not in buckets:
                buckets[key] = {'acc': acc, 'saldo': 0.0, 'bloque': bloque, 'code': code}
            buckets[key]['saldo'] += delta

        # Totales por bloque
        tot_ing = sum(b['saldo'] for b in buckets.values() if b['bloque'] == 'ingresos')
        tot_var = sum(b['saldo'] for b in buckets.values() if b['bloque'] == 'variables')
        tot_fij = sum(b['saldo'] for b in buckets.values() if b['bloque'] == 'fijos')

        lines_data = []
        for key, b in buckets.items():
            if abs(b['saldo']) < 0.005:
                continue
            tot_bloque = {'ingresos': tot_ing, 'variables': tot_var, 'fijos': tot_fij}[b['bloque']]
            pct_bloque = round(b['saldo'] / tot_bloque * 100, 2) if tot_bloque else 0.0
            pct_ingresos = round(b['saldo'] / tot_ing * 100, 2) if tot_ing else 0.0
            lines_data.append({
                'bloque':            b['bloque'],
                'account_id':        b['acc'].id,
                'codigo_cuenta':     b['code'],
                'nombre_cuenta':     b['acc'].name or '',
                'saldo':             round(b['saldo'], 2),
                'pct_sobre_bloque':  pct_bloque,
                'pct_sobre_ingresos': pct_ingresos,
                'date_from':         df,
                'date_to':           dt,
            })

        mb = tot_ing - tot_var
        res = tot_ing - tot_var - tot_fij
        kpis = {
            'total_ingresos':    round(tot_ing, 2),
            'total_variables':   round(tot_var, 2),
            'total_fijos':       round(tot_fij, 2),
            'margen_bruto':      round(mb, 2),
            'margen_bruto_pct':  round(mb / tot_ing * 100, 2) if tot_ing else 0.0,
            'resultado':         round(res, 2),
            'resultado_pct':     round(res / tot_ing * 100, 2) if tot_ing else 0.0,
            'num_ctas_ingresos':  sum(1 for d in lines_data if d['bloque'] == 'ingresos'),
            'num_ctas_variables': sum(1 for d in lines_data if d['bloque'] == 'variables'),
            'num_ctas_fijos':     sum(1 for d in lines_data if d['bloque'] == 'fijos'),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.pnl.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    @api.onchange('date_from', 'date_to')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_pnl_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_pnl_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'P&G — detalle por cuenta',
            'res_model': 'lira.pnl.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False, 'search_default_group_bloque': 1},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    def action_refresh(self):
        self._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def action_open(self):
        rec = self.create({'date_from': date.today().replace(month=1, day=1), 'date_to': date.today()})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'P&G por Periodos',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
