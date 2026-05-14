from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


class LiraDashboardAlerta(models.TransientModel):
    _name = 'lira.dashboard.alerta'
    _description = 'Alerta del dashboard financiero'
    _order = 'secuencia'

    dashboard_id = fields.Many2one('lira.dashboard', ondelete='cascade')
    secuencia    = fields.Integer()
    nivel        = fields.Selection([
        ('red',    'Crítico'),
        ('yellow', 'Atención'),
        ('info',   'OK'),
    ])
    mensaje      = fields.Char(string='Descripción', readonly=True)
    visible      = fields.Boolean(string='Mostrar', default=True)


class LiraDashboard(models.TransientModel):
    _name = 'lira.dashboard'
    _description = 'Dashboard Financiero'
    _rec_name = 'display_title'

    # TransientModel: los registros se auto-eliminan tras ~1h (tabla temporal)
    # _rec_name sobreescribe el breadcrumb del formulario

    display_title = fields.Char(default='Tablero de Contabilidad', readonly=True)
    date_from = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to   = fields.Date('Hasta', default=fields.Date.today)

    # ── Ratios de liquidez ─────────────────────────────────────────────────────
    ratio_liquidez_general   = fields.Float(digits=(16, 2), readonly=True)
    ratio_liquidez_inmediata = fields.Float(digits=(16, 2), readonly=True)
    ratio_tesoreria          = fields.Float(digits=(16, 2), readonly=True)
    ratio_solvencia          = fields.Float(digits=(16, 2), readonly=True)

    # ── Ratios de endeudamiento ────────────────────────────────────────────────
    ratio_endeudamiento = fields.Float(digits=(16, 1), readonly=True)
    ratio_autonomia     = fields.Float(digits=(16, 1), readonly=True)

    # ── Ratios de rentabilidad ─────────────────────────────────────────────────
    ratio_roe          = fields.Float(digits=(16, 1), readonly=True)
    ratio_roa          = fields.Float(digits=(16, 1), readonly=True)
    ratio_margen_bruto = fields.Float(digits=(16, 1), readonly=True)
    ratio_ebitda_pct   = fields.Float(digits=(16, 1), readonly=True)
    ratio_margen_neto  = fields.Float(digits=(16, 1), readonly=True)

    # ── Balance ────────────────────────────────────────────────────────────────
    activo_corriente    = fields.Float(readonly=True)
    activo_no_corriente = fields.Float(readonly=True)
    activo_total        = fields.Float(readonly=True)
    pasivo_corriente    = fields.Float(readonly=True)
    pasivo_no_corriente = fields.Float(readonly=True)
    pasivo_total        = fields.Float(readonly=True)
    patrimonio_neto     = fields.Float(readonly=True)

    # ── Cuenta de resultados ───────────────────────────────────────────────────
    ventas_periodo   = fields.Float(readonly=True)
    coste_ventas     = fields.Float(readonly=True)
    beneficio_bruto  = fields.Float(readonly=True)
    gastos_personal  = fields.Float(readonly=True)
    gastos_generales = fields.Float(readonly=True)
    amortizaciones   = fields.Float(readonly=True)
    ebitda               = fields.Float(readonly=True)
    ebit                 = fields.Float(readonly=True)
    resultado_financiero = fields.Float(readonly=True)
    beneficio_neto       = fields.Float(readonly=True)
    total_pasivo_pn      = fields.Float(readonly=True)

    # ── Variación vs periodo anterior (%) ─────────────────────────────────────
    var_ventas_pct = fields.Float(digits=(16, 1), readonly=True)
    var_ebitda_pct = fields.Float(digits=(16, 1), readonly=True)
    var_margen_pct = fields.Float(digits=(16, 1), readonly=True)

    # ── Tendencia legible (↑ +5.2 %, ↓ -3.1 %, → +0.5 %) ────────────────────
    trend_ventas = fields.Char(readonly=True)
    trend_ebitda = fields.Char(readonly=True)
    trend_margen = fields.Char(readonly=True)

    # ── Distribución de costes (% sobre ventas) ───────────────────────────────
    pct_coste_ventas = fields.Float(digits=(16, 1), readonly=True)
    pct_personal     = fields.Float(digits=(16, 1), readonly=True)
    pct_generales    = fields.Float(digits=(16, 1), readonly=True)
    pct_amort        = fields.Float(digits=(16, 1), readonly=True)
    pct_resultado    = fields.Float(digits=(16, 1), readonly=True)

    # ── Alertas inteligentes (One2many editable) ──────────────────────────────
    alerta_ids  = fields.One2many('lira.dashboard.alerta', 'dashboard_id', string='Alertas')
    hay_alertas = fields.Boolean(readonly=True)

    # ── Semáforos por ratio (green / yellow / red) ────────────────────────────
    sem_liquidez      = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_liq_inmediata = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_tesoreria     = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_solvencia     = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_endeudamiento = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_roe           = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_roa           = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_margen_bruto  = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_ebitda        = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)
    sem_margen_neto   = fields.Selection([('green', ''), ('yellow', ''), ('red', '')], readonly=True)

    # ── Ciclo de maduración ───────────────────────────────────────────────────
    pmc        = fields.Float(digits=(16, 1), readonly=True)
    pmc_real   = fields.Float(digits=(16, 1), readonly=True)
    pmp        = fields.Float(digits=(16, 1), readonly=True)
    pmp_real   = fields.Float(digits=(16, 1), readonly=True)
    pma        = fields.Float(digits=(16, 1), readonly=True)
    pma_real   = fields.Float(digits=(16, 1), readonly=True)
    tms_real   = fields.Float(digits=(16, 1), readonly=True)
    ciclo_caja = fields.Float(digits=(16, 1), readonly=True)   # PMC + PMA - PMP
    tms_dias   = fields.Float(digits=(16, 1), readonly=True)   # Término medio de servicio
    ciclo_semaforo = fields.Selection([
        ('green',  'Óptimo (< 30 días)'),
        ('yellow', 'Aceptable (30–60 días)'),
        ('red',    'Crítico (> 60 días)'),
    ], readonly=True)

    # ══ HELPERS ═══════════════════════════════════════════════════════════════

    def _q(self, df=None, dt=None):
        """
        Un único SELECT agregado sobre account_move_line para la ventana temporal dada.

        Devuelve tres diccionarios de saldo neto (debit – credit):
          by_type  → clave = account_type de Odoo  (p.ej. 'asset_receivable')
          by_code2 → clave = primeros 2 dígitos     (p.ej. '64', '62')
          by_code1 → clave = primer dígito          (p.ej. '3' para existencias)

        Patrón de optimización:
          La versión anterior hacía un search() por cada ratio (~13 queries por
          periodo, 26 en total con el periodo anterior). Aquí un solo GROUP BY
          resuelve todo: el motor SQL agrega en disco, no en Python.
        """
        cr    = self.env.cr
        cid   = self.env.company.id
        params = [cid]
        date_clause = ''
        if df:
            date_clause += ' AND aml.date >= %s'
            params.append(df)
        if dt:
            date_clause += ' AND aml.date <= %s'
            params.append(dt)

        cr.execute(f"""
            SELECT aa.account_type,
                   LEFT(aa.code_store->>'1', 2)       AS c2,
                   LEFT(aa.code_store->>'1', 1)       AS c1,
                   SUM(aml.debit) - SUM(aml.credit)  AS net
            FROM   account_move_line  aml
            JOIN   account_account    aa ON aa.id = aml.account_id
            JOIN   account_move       am ON am.id = aml.move_id
            WHERE  am.state     = 'posted'
              AND  aml.company_id = %s
              {date_clause}
            GROUP  BY aa.account_type, LEFT(aa.code_store->>'1', 2), LEFT(aa.code_store->>'1', 1)
        """, params)

        by_type, by_code2, by_code1 = {}, {}, {}
        for atype, c2, c1, net in cr.fetchall():
            n = net or 0.0
            by_type[atype] = by_type.get(atype, 0.0) + n
            by_code2[c2]   = by_code2.get(c2, 0.0)   + n
            by_code1[c1]   = by_code1.get(c1, 0.0)   + n
        return by_type, by_code2, by_code1

    def _sem(self, val, green_min=None, yellow_min=None, green_max=None, yellow_max=None):
        """
        Semáforo de dos variantes:
          - green_min/yellow_min: ratios donde mayor es mejor (liquidez, márgenes).
          - green_max/yellow_max: ratios donde menor es mejor (endeudamiento).
        """
        if green_min is not None:
            if val >= green_min:   return 'green'
            if val >= yellow_min:  return 'yellow'
            return 'red'
        if green_max is not None:
            if val <= green_max:   return 'green'
            if val <= yellow_max:  return 'yellow'
            return 'red'
        return 'red'

    def _trend(self, pct):
        """Flecha de tendencia + variación porcentual respecto al periodo anterior."""
        if pct > 2:   return f'↑ +{pct:.1f}%'
        if pct < -2:  return f'↓ {pct:.1f}%'
        return f'→ {pct:+.1f}%'

    def _var(self, curr, prev):
        """Variación porcentual segura (devuelve 0 si no hay base)."""
        return round((curr - prev) / abs(prev) * 100, 1) if prev else 0.0

    # ══ COMPUTE PRINCIPAL ═════════════════════════════════════════════════════

    @api.onchange('date_from', 'date_to')
    def _compute_all(self):
        for rec in self:
            df = rec.date_from or date.today().replace(month=1, day=1)
            dt = rec.date_to   or date.today()

            # Periodo anterior: misma duración, inmediatamente antes de df
            span    = (dt - df).days
            df_prev = df - relativedelta(days=span + 1)
            dt_prev = df - relativedelta(days=1)

            # ── Query 1/3 · Balance de situación (acumulado, sin filtro fecha) ──
            # El balance no lleva fecha porque es una foto del momento actual,
            # no un flujo de periodo como la cuenta de resultados.
            bs, bs2, bs1 = rec._q()

            def t(*types):
                return sum(bs.get(x, 0.0) for x in types)

            clientes    =  t('asset_receivable')
            tesoreria   =  t('asset_cash')
            # asset_receivable y asset_cash son tipos propios en Odoo, distintos de asset_current
            activo_c    =  t('asset_receivable', 'asset_cash', 'asset_current')
            activo_nc   =  t('asset_non_current', 'asset_fixed')
            activo_t    = activo_c + activo_nc
            # Pasivos son cuentas de naturaleza acreedora → raw net es negativo → negamos
            proveedores = -t('liability_payable')
            pasivo_c    = -t('liability_payable', 'liability_current')
            pasivo_nc   = -t('liability_non_current')
            pasivo_t    = pasivo_c + pasivo_nc
            patrimonio  = activo_t - pasivo_t
            # Existencias: grupo 3 del PGC (300xxx–399xxx), primer dígito '3'
            existencias = bs1.get('3', 0.0)

            # ── Query 2/3 · Cuenta de resultados — periodo actual ───────────────
            pl, pl2, _ = rec._q(df=df, dt=dt)

            # Ingresos de explotación (cuentas acreedoras → net negativo → negamos)
            # Solo grupo 70-75 para el EBITDA; 76-77 son financieros y van aparte
            ventas     = -(pl2.get('70', 0.0))
            otros_ing  = -(pl2.get('71', 0.0) + pl2.get('73', 0.0)
                           + pl2.get('74', 0.0) + pl2.get('75', 0.0))
            ingresos_op = ventas + otros_ing

            # COGS: compras (60) + variación existencias materias (61)
            coste_v    = pl2.get('60', 0.0) + pl2.get('61', 0.0)

            # Gastos operativos (cuentas deudoras → net positivo)
            g_personal = pl2.get('64', 0.0)
            g_general  = pl2.get('62', 0.0) + pl2.get('63', 0.0) + pl2.get('65', 0.0)
            amort      = pl2.get('68', 0.0)

            # Resultado financiero (76=ingresos fin., 66=gastos fin.)
            res_financiero = -(pl2.get('76', 0.0)) - pl2.get('66', 0.0)

            margen_b   = ingresos_op - coste_v
            ebitda_val = margen_b - g_personal - g_general
            ebit_val   = ebitda_val - amort
            beneficio  = ebit_val + res_financiero

            # ── Query 3/3 · Cuenta de resultados — periodo anterior ─────────────
            pp, pp2, _ = rec._q(df=df_prev, dt=dt_prev)

            ventas_p   = -(pp2.get('70', 0.0))
            otros_p    = -(pp2.get('71', 0.0) + pp2.get('73', 0.0)
                           + pp2.get('74', 0.0) + pp2.get('75', 0.0))
            ingresos_p = ventas_p + otros_p
            coste_p    = pp2.get('60', 0.0) + pp2.get('61', 0.0)
            margen_p   = ingresos_p - coste_p
            ebitda_p   = margen_p - pp2.get('64', 0.0) - pp2.get('62', 0.0) - pp2.get('63', 0.0) - pp2.get('65', 0.0)

            # ── Persistir balance y P&L ─────────────────────────────────────────
            rec.activo_corriente    = activo_c
            rec.activo_no_corriente = activo_nc
            rec.activo_total        = activo_t
            rec.pasivo_corriente    = pasivo_c
            rec.pasivo_no_corriente = pasivo_nc
            rec.pasivo_total        = pasivo_t
            rec.patrimonio_neto     = patrimonio
            rec.ventas_periodo      = ingresos_op
            rec.coste_ventas        = coste_v
            rec.beneficio_bruto     = margen_b
            rec.gastos_personal     = g_personal
            rec.gastos_generales    = g_general
            rec.amortizaciones      = amort
            rec.ebitda               = ebitda_val
            rec.ebit                 = ebit_val
            rec.resultado_financiero = res_financiero
            rec.beneficio_neto       = beneficio
            rec.total_pasivo_pn      = patrimonio + pasivo_c + pasivo_nc

            # ── Tendencias ──────────────────────────────────────────────────────
            vv = rec._var(ingresos_op, ingresos_p)
            ve = rec._var(ebitda_val, ebitda_p)
            vm = rec._var(
                margen_b / ingresos_op * 100 if ingresos_op else 0,
                margen_p / ingresos_p * 100  if ingresos_p  else 0,
            )
            rec.var_ventas_pct = vv;  rec.trend_ventas = rec._trend(vv)
            rec.var_ebitda_pct = ve;  rec.trend_ebitda = rec._trend(ve)
            rec.var_margen_pct = vm;  rec.trend_margen = rec._trend(vm)

            # ── Ratios ──────────────────────────────────────────────────────────
            rlg  = round(activo_c / pasivo_c, 2)                 if pasivo_c   else 0.0
            rli  = round((activo_c - existencias) / pasivo_c, 2) if pasivo_c   else 0.0
            rt   = round(tesoreria / pasivo_c, 2)                if pasivo_c   else 0.0
            rs   = round(activo_t / pasivo_t, 2)                 if pasivo_t   else 0.0
            rend = round(pasivo_t / activo_t * 100, 1)           if activo_t   else 0.0
            raut = round(patrimonio / activo_t * 100, 1)         if activo_t   else 0.0
            roe  = round(beneficio / patrimonio * 100, 1)        if patrimonio > 0 else 0.0
            roa  = round(beneficio / activo_t * 100, 1)         if activo_t   else 0.0
            rmb  = round(margen_b   / ingresos_op * 100, 1) if ingresos_op else 0.0
            rebi = round(ebitda_val / ingresos_op * 100, 1) if ingresos_op else 0.0
            rmn  = round(beneficio  / ingresos_op * 100, 1) if ingresos_op else 0.0

            rec.ratio_liquidez_general   = rlg
            rec.ratio_liquidez_inmediata = rli
            rec.ratio_tesoreria          = rt
            rec.ratio_solvencia          = rs
            rec.ratio_endeudamiento      = rend
            rec.ratio_autonomia          = raut
            rec.ratio_roe                = roe
            rec.ratio_roa                = roa
            rec.ratio_margen_bruto       = rmb
            rec.ratio_ebitda_pct         = rebi
            rec.ratio_margen_neto        = rmn

            # ── Semáforos ───────────────────────────────────────────────────────
            S = rec._sem
            rec.sem_liquidez      = S(rlg,  green_min=1.5,  yellow_min=1.0)
            rec.sem_liq_inmediata = S(rli,  green_min=1.0,  yellow_min=0.75)
            rec.sem_tesoreria     = S(rt,   green_min=0.3,  yellow_min=0.1)
            rec.sem_solvencia     = S(rs,   green_min=2.0,  yellow_min=1.0)
            rec.sem_endeudamiento = S(rend, green_max=50.0, yellow_max=70.0)
            rec.sem_roe           = S(roe,  green_min=10.0, yellow_min=0.0)
            rec.sem_roa           = S(roa,  green_min=5.0,  yellow_min=0.0)
            rec.sem_margen_bruto  = S(rmb,  green_min=40.0, yellow_min=20.0)
            rec.sem_ebitda        = S(rebi, green_min=15.0, yellow_min=5.0)
            rec.sem_margen_neto   = S(rmn,  green_min=10.0, yellow_min=0.0)

            # ── Distribución de costes (% sobre ventas) ─────────────────────────
            def pct(v): return round(v / ingresos_op * 100, 1) if ingresos_op else 0.0
            rec.pct_coste_ventas = pct(coste_v)
            rec.pct_personal     = pct(g_personal)
            rec.pct_generales    = pct(g_general)
            rec.pct_amort        = pct(amort)
            rec.pct_resultado    = rmn

            # ── Alertas inteligentes (10 condiciones fijas, el usuario activa/desactiva) ──
            def _niv(val, red_fn, yel_fn, msg_red, msg_yel, msg_ok):
                if red_fn(val):
                    return ('red', msg_red)
                if yel_fn(val):
                    return ('yellow', msg_yel)
                return ('info', msg_ok)

            condiciones = [
                _niv(rt,   lambda v: v < 0.1,  lambda v: v < 0.3,
                     f'Tesorería crítica — ratio {rt:.2f} (mín. recomendado 0.30)',
                     f'Tesorería ajustada — ratio {rt:.2f} (recomendado > 0.30)',
                     f'Tesorería correcta — ratio {rt:.2f}'),
                _niv(rlg,  lambda v: v < 1.0,  lambda v: v < 1.5,
                     f'Liquidez general crítica — ratio {rlg:.2f} (mín. 1.0)',
                     f'Liquidez general mejorable — ratio {rlg:.2f} (óptimo > 1.5)',
                     f'Liquidez general correcta — ratio {rlg:.2f}'),
                _niv(rli,  lambda v: v < 0.75, lambda v: v < 1.0,
                     f'Liquidez inmediata crítica — ratio {rli:.2f} (mín. 0.75)',
                     f'Liquidez inmediata mejorable — ratio {rli:.2f} (óptimo > 1.0)',
                     f'Liquidez inmediata correcta — ratio {rli:.2f}'),
                _niv(rs,   lambda v: v < 1.0,  lambda v: v < 1.5,
                     f'Solvencia crítica — ratio {rs:.2f} (mín. 1.0)',
                     f'Solvencia mejorable — ratio {rs:.2f} (óptimo > 1.5)',
                     f'Solvencia correcta — ratio {rs:.2f}'),
                _niv(rend, lambda v: v > 80,   lambda v: v > 60,
                     f'Endeudamiento muy elevado — {rend:.1f}% (máx. recomendado 70%)',
                     f'Endeudamiento elevado — {rend:.1f}% (recomendado < 60%)',
                     f'Endeudamiento controlado — {rend:.1f}%'),
                _niv(rmb,  lambda v: v < 0,    lambda v: v < 20,
                     'Margen bruto negativo — el coste supera los ingresos',
                     f'Margen bruto bajo — {rmb:.1f}% (recomendado > 40%)',
                     f'Margen bruto correcto — {rmb:.1f}%'),
                _niv(roe,  lambda v: v < 0,    lambda v: v < 5,
                     f'ROE negativo — la empresa destruye valor ({roe:.1f}%)',
                     f'ROE bajo — {roe:.1f}% (recomendado > 10%)',
                     f'ROE positivo — {roe:.1f}%'),
                _niv(roa,  lambda v: v < 0,    lambda v: v < 3,
                     f'ROA negativo — activos no rentables ({roa:.1f}%)',
                     f'ROA bajo — {roa:.1f}% (recomendado > 5%)',
                     f'ROA positivo — {roa:.1f}%'),
                _niv(rebi, lambda v: v < 0,    lambda v: v < 5,
                     f'EBITDA negativo — operaciones con pérdidas ({rebi:.1f}%)',
                     f'EBITDA bajo — {rebi:.1f}% (recomendado > 15%)',
                     f'EBITDA positivo — {rebi:.1f}%'),
                _niv(vv,   lambda v: v < -15,  lambda v: v < -5,
                     f'Caída grave de ventas — {vv:+.1f}% vs periodo anterior',
                     f'Caída de ventas — {vv:+.1f}% vs periodo anterior',
                     f'Ventas estables/creciendo — {vv:+.1f}% vs periodo anterior'),
            ]

            alerta_vals = [(5,)] + [
                (0, 0, {'secuencia': i + 1, 'nivel': niv, 'mensaje': msg,
                        'visible': niv in ('red', 'yellow')})
                for i, (niv, msg) in enumerate(condiciones)
            ]
            rec.alerta_ids = alerta_vals
            rec.hay_alertas = any(niv in ('red', 'yellow') for niv, _ in condiciones)

            # ── Ciclo de maduración ─────────────────────────────────────────────
            # PMC = (saldo clientes / ventas periodo) × días; similar para PMP y PMA
            dias = max((dt - df).days, 1)
            rec.pmc        = round(clientes    / ingresos_op * dias, 1) if ingresos_op > 0 else 0.0
            rec.pmp        = round(proveedores / coste_v     * dias, 1) if coste_v     > 0 else 0.0
            rec.pma        = round(existencias / coste_v     * dias, 1) if coste_v     > 0 else 0.0
            rec.ciclo_caja = rec.pmc + rec.pma - rec.pmp
            rec.ciclo_semaforo = (
                'green'  if rec.ciclo_caja < 30  else
                'yellow' if rec.ciclo_caja <= 60 else 'red'
            )

            cr = self.env.cr
            cid_real = self.env.company.id

            # PMC real: promedio (fecha_cobro − fecha_factura) facturas cliente cobradas
            try:
                cr.execute("""
                    SELECT AVG(aml_pay.date - am.invoice_date)
                    FROM account_move am
                    JOIN account_move_line aml_inv ON aml_inv.move_id = am.id
                    JOIN account_account aa ON aa.id = aml_inv.account_id
                         AND aa.account_type = 'asset_receivable'
                    JOIN account_partial_reconcile apr ON apr.debit_move_id = aml_inv.id
                    JOIN account_move_line aml_pay ON aml_pay.id = apr.credit_move_id
                    WHERE am.move_type = 'out_invoice' AND am.state = 'posted'
                      AND am.company_id = %s AND am.invoice_date IS NOT NULL
                      AND aml_pay.date >= am.invoice_date
                """, [cid_real])
                row = cr.fetchone()
                rec.pmc_real = round(float(row[0]), 1) if row and row[0] is not None else 0.0
            except Exception:
                rec.pmc_real = 0.0

            # PMP real: promedio (fecha_pago − fecha_factura) facturas proveedor pagadas
            try:
                cr.execute("""
                    SELECT AVG(aml_pay.date - am.invoice_date)
                    FROM account_move am
                    JOIN account_move_line aml_inv ON aml_inv.move_id = am.id
                    JOIN account_account aa ON aa.id = aml_inv.account_id
                         AND aa.account_type = 'liability_payable'
                    JOIN account_partial_reconcile apr ON apr.credit_move_id = aml_inv.id
                    JOIN account_move_line aml_pay ON aml_pay.id = apr.debit_move_id
                    WHERE am.move_type = 'in_invoice' AND am.state = 'posted'
                      AND am.company_id = %s AND am.invoice_date IS NOT NULL
                      AND aml_pay.date >= am.invoice_date
                """, [cid_real])
                row = cr.fetchone()
                rec.pmp_real = round(float(row[0]), 1) if row and row[0] is not None else 0.0
            except Exception:
                rec.pmp_real = 0.0

            # PMA real: promedio (fecha_entrega − fecha_recepción) por producto
            try:
                cr.execute("""
                    SELECT AVG(sm_out.date::date - sm_in_last.date::date)
                    FROM stock_move sm_out
                    JOIN stock_location sl_src ON sl_src.id = sm_out.location_id
                         AND sl_src.usage = 'internal'
                    JOIN stock_location sl_dst ON sl_dst.id = sm_out.location_dest_id
                         AND sl_dst.usage = 'customer'
                    JOIN LATERAL (
                        SELECT sm_in.date
                        FROM stock_move sm_in
                        JOIN stock_location sl_in_dst ON sl_in_dst.id = sm_in.location_dest_id
                             AND sl_in_dst.usage = 'internal'
                        WHERE sm_in.product_id = sm_out.product_id
                          AND sm_in.state = 'done'
                          AND sm_in.company_id = %s
                          AND sm_in.date <= sm_out.date
                        ORDER BY sm_in.date DESC
                        LIMIT 1
                    ) sm_in_last ON TRUE
                    WHERE sm_out.state = 'done'
                      AND sm_out.company_id = %s
                      AND sm_out.date::date >= sm_in_last.date::date
                """, [cid_real, cid_real])
                row = cr.fetchone()
                rec.pma_real = round(float(row[0]), 1) if row and row[0] is not None else 0.0
            except Exception:
                rec.pma_real = 0.0

            # TMS real: promedio (fecha_entrega − fecha_pedido) de pedidos entregados
            try:
                cr.execute("""
                    SELECT AVG(sm.date::date - so.date_order::date)
                    FROM sale_order so
                    JOIN sale_order_line sol ON sol.order_id = so.id
                    JOIN stock_move sm ON sm.sale_line_id = sol.id
                    JOIN stock_location sl_dst ON sl_dst.id = sm.location_dest_id
                         AND sl_dst.usage = 'customer'
                    WHERE so.state IN ('sale', 'done')
                      AND sm.state = 'done'
                      AND so.company_id = %s
                      AND sm.date::date >= so.date_order::date
                """, [cid_real])
                row = cr.fetchone()
                rec.tms_real = round(float(row[0]), 1) if row and row[0] is not None else 0.0
            except Exception:
                rec.tms_real = 0.0

            # Término medio de servicio (fórmula existente: pedido → primera factura): días desde pedido hasta primera factura emitida
            # Se calcula aparte porque no viene de account_move_line sino de sale.order
            try:
                orders = self.env['sale.order'].search([
                    ('state', 'in', ['sale', 'done']),
                    ('date_order', '>=', str(df)),
                    ('date_order', '<=', str(dt)),
                    ('company_id', '=', self.env.company.id),
                ])
                deltas = []
                for o in orders:
                    inv = o.invoice_ids.filtered(lambda i: i.state == 'posted' and i.invoice_date)
                    if inv:
                        deltas.append((min(inv.mapped('invoice_date')) - o.date_order.date()).days)
                rec.tms_dias = round(sum(deltas) / len(deltas), 1) if deltas else 0.0
            except Exception:
                rec.tms_dias = 0.0

    # ══ DRILLDOWNS ════════════════════════════════════════════════════════════
    # Abre account.move.line filtrado por grupo contable y periodo seleccionado.
    # Solo usa account.move.line + account.account (módulo base account,
    # disponible en Community y Enterprise).

    def _drill(self, title, code_prefixes):
        """Acción genérica: abre apuntes contables filtrados por prefijos de cuenta."""
        df = self.date_from or date.today().replace(month=1, day=1)
        dt = self.date_to   or date.today()

        or_parts = [('account_id.code', '=like', p + '%') for p in code_prefixes]
        if len(or_parts) == 1:
            code_domain = [or_parts[0]]
        else:
            code_domain = []
            for _ in range(len(or_parts) - 1):
                code_domain.append('|')
            code_domain += or_parts

        domain = [
            ('company_id', '=', self.env.company.id),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', df),
            ('date', '<=', dt),
        ] + code_domain

        return {
            'type':      'ir.actions.act_window',
            'name':      title,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain':    domain,
            'context': {
                'search_default_group_by_account': 1,
                'expand': 1,
            },
        }

    def action_drill_ventas(self):
        return self._drill('Ingresos de explotación', ['7'])

    def action_drill_coste_ventas(self):
        return self._drill('Coste de ventas', ['60', '61'])

    def action_drill_personal(self):
        return self._drill('Gastos de personal', ['64'])

    def action_drill_generales(self):
        return self._drill('Gastos generales', ['62', '63'])

    def action_drill_amortizaciones(self):
        return self._drill('Amortizaciones', ['68'])

    def action_drill_financiero(self):
        return self._drill('Resultado financiero', ['66', '76'])

    # ══ ACCIONES ══════════════════════════════════════════════════════════════

    def action_refresh(self):
        """Botón 'Actualizar' del formulario — recalcula y vuelve al mismo registro."""
        self._compute_all()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_forecast(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Previsión de liquidez',
            'res_model': 'lira.forecast',
            'view_mode': 'graph,list',
            'target': 'current',
        }

    @api.model
    def action_open_dashboard(self):
        """
        Punto de entrada desde el menú.
        Crea un nuevo registro TransientModel, calcula todo y abre el formulario.
        Se usa ir.actions.server en el XML para poder llamarlo como @api.model.
        """
        rec = self.create({
            'date_from': date.today().replace(month=1, day=1),
            'date_to': date.today(),
        })
        rec._compute_all()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tablero de Contabilidad',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
