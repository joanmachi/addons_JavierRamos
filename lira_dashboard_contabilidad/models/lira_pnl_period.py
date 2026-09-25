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
        ('facturacion', 'Facturación'),
        ('otros_ingresos', 'Otros ingresos'),
        ('variacion', 'Variación de existencias'),
        ('variables_directos', 'Variables directos'),
        ('semivariables', 'Semivariables'),
        ('fijos_operativos', 'Fijos operativos'),
        ('estructura', 'Estructura / Dirección'),
        ('amortizaciones', 'Amortizaciones'),
        ('financieros', 'Gastos financieros'),
        ('ingresos_financieros', 'Ingresos financieros'),
        ('sin_clasificar', 'Sin clasificar'),
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

    # KPIs — la cascada por bloques de la clasificación del asesor
    total_facturacion = fields.Float('Facturación (€)', readonly=True)
    total_variables   = fields.Float('Variables directos (€)', readonly=True)
    variables_pct     = fields.Float('Variables directos (% s/facturación)', readonly=True)
    total_semivariables = fields.Float('Semivariables (€)', readonly=True)
    semivariables_pct = fields.Float('Semivariables (% s/facturación)', readonly=True)
    total_fijos_op    = fields.Float('Fijos operativos (€)', readonly=True)
    fijos_op_pct      = fields.Float('Fijos operativos (% s/facturación)', readonly=True)
    total_estructura  = fields.Float('Estructura / Dirección (€)', readonly=True)
    estructura_pct    = fields.Float('Estructura (% s/facturación)', readonly=True)
    total_otros_ing   = fields.Float('Otros ingresos (€)', readonly=True)
    total_variacion   = fields.Float('Variación de existencias (€)', readonly=True)
    ebitda            = fields.Float('EBITDA (€)', readonly=True,
        help='Facturación + otros ingresos + variación de existencias − los cuatro bloques de coste')
    ebitda_pct        = fields.Float('EBITDA (% s/facturación)', readonly=True)
    total_amortizaciones = fields.Float('Amortizaciones (€)', readonly=True)
    ebit              = fields.Float('EBIT (€)', readonly=True, help='EBITDA − amortizaciones')
    total_financieros = fields.Float('Gastos financieros (€)', readonly=True)
    total_ing_financieros = fields.Float('Ingresos financieros (€)', readonly=True)
    resultado         = fields.Float('Resultado (€)', readonly=True)
    resultado_pct     = fields.Float('Resultado (%)', readonly=True)
    total_sin_clasificar = fields.Float('Sin clasificar (€)', readonly=True,
        help='Gasto que no está en la clasificación del asesor ni es amortización o financiero. '
             'Debería tender a cero: si crece, hay cuentas nuevas por clasificar.')

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

        # Clasificación del asesor: {código de cuenta: bloque}
        mapa = self.env['lira.cuenta.bloque'].mapa()

        buckets = {}
        for ln in aml_lines:
            acc = ln.account_id
            code = acc.code or ''
            if code.startswith('7'):
                delta = (ln.credit or 0.0) - (ln.debit or 0.0)
                if code.startswith('71'):
                    bloque = 'variacion'
                elif code.startswith('70'):
                    bloque = 'facturacion'
                elif code.startswith('76'):
                    bloque = 'ingresos_financieros'
                else:
                    bloque = 'otros_ingresos'
            elif code.startswith('6'):
                delta = (ln.debit or 0.0) - (ln.credit or 0.0)
                if code in mapa:
                    bloque = mapa[code]
                elif code.startswith('68'):
                    bloque = 'amortizaciones'
                elif code.startswith('66'):
                    bloque = 'financieros'
                else:
                    bloque = 'sin_clasificar'
            else:
                continue
            key = acc.id
            if key not in buckets:
                buckets[key] = {'acc': acc, 'saldo': 0.0, 'bloque': bloque, 'code': code}
            buckets[key]['saldo'] += delta

        def tot(bloque):
            return sum(b['saldo'] for b in buckets.values() if b['bloque'] == bloque)

        t_fact = tot('facturacion')
        t_otros = tot('otros_ingresos')
        t_varex = tot('variacion')
        t_var = tot('variables_directos')
        t_semi = tot('semivariables')
        t_fij = tot('fijos_operativos')
        t_est = tot('estructura')
        t_amort = tot('amortizaciones')
        t_fin = tot('financieros')
        t_ingfin = tot('ingresos_financieros')
        t_sin = tot('sin_clasificar')

        totales = {'facturacion': t_fact, 'otros_ingresos': t_otros, 'variacion': t_varex,
                   'variables_directos': t_var, 'semivariables': t_semi,
                   'fijos_operativos': t_fij, 'estructura': t_est,
                   'amortizaciones': t_amort, 'financieros': t_fin,
                   'ingresos_financieros': t_ingfin, 'sin_clasificar': t_sin}

        lines_data = []
        for key, b in buckets.items():
            if abs(b['saldo']) < 0.005:
                continue
            tot_bloque = totales.get(b['bloque'], 0.0)
            lines_data.append({
                'bloque':            b['bloque'],
                'account_id':        b['acc'].id,
                'codigo_cuenta':     b['code'],
                'nombre_cuenta':     b['acc'].name or '',
                'saldo':             round(b['saldo'], 2),
                'pct_sobre_bloque':  round(b['saldo'] / tot_bloque * 100, 2) if tot_bloque else 0.0,
                'pct_sobre_ingresos': round(b['saldo'] / t_fact * 100, 2) if t_fact else 0.0,
                'date_from':         df,
                'date_to':           dt,
            })

        pct = lambda x: round(x / t_fact * 100, 2) if t_fact else 0.0
        ebitda = t_fact + t_otros + t_varex - t_var - t_semi - t_fij - t_est - t_sin
        ebit = ebitda - t_amort
        res = ebit - t_fin + t_ingfin
        kpis = {
            'total_facturacion':   round(t_fact, 2),
            'total_variables':     round(t_var, 2),
            'variables_pct':       pct(t_var),
            'total_semivariables': round(t_semi, 2),
            'semivariables_pct':   pct(t_semi),
            'total_fijos_op':      round(t_fij, 2),
            'fijos_op_pct':        pct(t_fij),
            'total_estructura':    round(t_est, 2),
            'estructura_pct':      pct(t_est),
            'total_otros_ing':     round(t_otros, 2),
            'total_variacion':     round(t_varex, 2),
            'ebitda':              round(ebitda, 2),
            'ebitda_pct':          pct(ebitda),
            'total_amortizaciones': round(t_amort, 2),
            'ebit':                round(ebit, 2),
            'total_financieros':   round(t_fin, 2),
            'total_ing_financieros': round(t_ingfin, 2),
            'resultado':           round(res, 2),
            'resultado_pct':       pct(res),
            'total_sin_clasificar': round(t_sin, 2),
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

    def action_evolucion_mensual(self):
        """La misma cascada, pero desglosada mes a mes en el rango elegido."""
        self.ensure_one()
        return self.env['lira.evolucion.coste'].action_open(self.date_from, self.date_to)

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
