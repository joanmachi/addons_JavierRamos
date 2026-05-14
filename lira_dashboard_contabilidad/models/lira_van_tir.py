from odoo import models, fields, api


class LiraCashFlowLine(models.Model):
    _name = 'lira.cash.flow.line'
    _description = 'Flujo de caja para VAN/TIR'
    _order = 'periodo'

    wizard_id   = fields.Many2one('lira.van.tir', ondelete='cascade')
    periodo     = fields.Integer('Período', required=True,
        help='Número de período (año 1, 2, 3... o mes 1, 2, 3... según la configuración del proyecto)')
    descripcion = fields.Char('Descripción',
        help='Descripción libre del flujo de caja de este período')
    ingresos    = fields.Float('Ingresos esperados (€)', digits=(16, 2),
        help='Ingresos estimados para este período del proyecto (ventas, ahorros, etc.)')
    gastos      = fields.Float('Gastos esperados (€)', digits=(16, 2),
        help='Gastos estimados para este período del proyecto (costes operativos, mantenimiento, etc.)')
    flujo_neto  = fields.Float('Flujo neto (€)', digits=(16, 2), compute='_compute_flujo', store=True,
        help='Flujo de caja neto del período: ingresos esperados menos gastos esperados')

    @api.depends('ingresos', 'gastos')
    def _compute_flujo(self):
        for r in self:
            r.flujo_neto = r.ingresos - r.gastos


class LiraVanTir(models.Model):
    _name = 'lira.van.tir'
    _description = 'Calculadora VAN/TIR — Análisis de inversiones'
    _rec_name = 'nombre'

    nombre            = fields.Char('Nombre del proyecto', default='Nueva inversión',
        help='Nombre descriptivo de la inversión o proyecto que se está evaluando')
    descripcion       = fields.Text('Descripción',
        help='Descripción detallada del proyecto, hipótesis y supuestos utilizados en el análisis')
    tipo_periodo      = fields.Selection([
        ('anos',  'Años'),
        ('meses', 'Meses'),
    ], string='Tipo de período', default='anos', required=True,
        help='Unidad temporal de los flujos de caja. Si elige Meses, la tasa de descuento anual se divide automáticamente entre 12 para obtener la tasa mensual efectiva')
    inversion_inicial = fields.Float('Inversión inicial (€)', required=True, default=0.0,
        help='Desembolso inicial del proyecto en el período 0. Se resta automáticamente al primer flujo en el cálculo')
    valor_residual    = fields.Float('Valor residual (€)', default=0.0,
        help='Valor de recuperación al final de la vida útil del proyecto (venta de activos, etc.). Se suma al flujo del último período')
    tasa_descuento    = fields.Float('Tasa de descuento anual (%)', default=8.0,
        help='Tasa de descuento anual. Si los períodos son meses, se aplicará tasa/12 por período. Suele ser el WACC de la empresa (8% es un valor habitual para PYMES)')
    tasa_periodo      = fields.Float('Tasa por período (%)', readonly=True, digits=(16, 4),
        compute='_compute_tasa_periodo', store=False,
        help='Tasa de descuento efectiva por período: si los períodos son Años = tasa anual; si son Meses = tasa anual / 12')

    cash_flow_ids = fields.One2many('lira.cash.flow.line', 'wizard_id', string='Flujos de caja por período')

    @api.depends('tasa_descuento', 'tipo_periodo')
    def _compute_tasa_periodo(self):
        for r in self:
            if r.tipo_periodo == 'meses':
                r.tasa_periodo = round(r.tasa_descuento / 12, 4)
            else:
                r.tasa_periodo = r.tasa_descuento

    van                 = fields.Float('VAN (€)', readonly=True, digits=(16, 2),
        help='Valor Actual Neto: suma de todos los flujos de caja actualizados a la tasa de descuento menos la inversión inicial. VAN > 0 = la inversión crea valor. Fórmula: Σ(Flujo_t / (1+r)^t) - Inversión_inicial')
    tir                 = fields.Float('TIR (%)', readonly=True, digits=(16, 2),
        help='Tasa Interna de Retorno: es la tasa de descuento a la que el VAN vale cero. Si TIR > tasa de descuento la inversión es rentable. Se calcula por bisección numérica')
    payback_anos        = fields.Float('Payback (años)', readonly=True, digits=(16, 1),
        help='Periodo de recuperación de la inversión: número de años que tarda en recuperarse el desembolso inicial con los flujos de caja acumulados')
    indice_rentabilidad = fields.Float('Índice de rentabilidad', readonly=True, digits=(16, 2),
        help='Relación entre el valor presente de los flujos positivos y la inversión inicial. Índice > 1 = inversión rentable. Fórmula: VP(flujos positivos) / inversión inicial')
    decision            = fields.Char('Decisión', readonly=True,
        help='Recomendación automática basada en el VAN y la TIR: VIABLE (VAN > 0 y TIR > tasa), ACEPTABLE, MARGINAL o NO VIABLE')
    decision_color      = fields.Selection([
        ('green',  'Viable'),
        ('yellow', 'Revisar'),
        ('red',    'No viable'),
    ], readonly=True)
    beneficio_total  = fields.Float('Beneficio total (€)', readonly=True, digits=(16, 2),
        help='Suma aritmética de todos los flujos incluyendo la inversión inicial (sin actualizar). Muestra el beneficio bruto total del proyecto')
    flujo_acumulado  = fields.Float('Flujo acumulado (€)', readonly=True, digits=(16, 2),
        help='Suma total de todos los flujos de caja del proyecto incluyendo la inversión inicial')

    # ── Cálculo principal ─────────────────────────────────────────────────────

    def _calcular(self):
        """Devuelve un dict con todos los resultados para self (un registro)."""
        rec = self
        flujos_raw = [l.flujo_neto for l in rec.cash_flow_ids.sorted('periodo')]

        if not flujos_raw or rec.inversion_inicial <= 0:
            return {
                'van': 0.0, 'tir': 0.0,
                'payback_anos': 0.0, 'indice_rentabilidad': 0.0,
                'beneficio_total': 0.0, 'flujo_acumulado': 0.0,
                'decision': 'Introduce la inversión inicial y los flujos de caja',
                'decision_color': 'yellow',
            }

        flujos_raw = list(flujos_raw)
        flujos_raw[-1] += rec.valor_residual
        flujos = [-rec.inversion_inicial] + flujos_raw

        # tasa por período: anual si años, anual/12 si meses
        divisor = 12 if rec.tipo_periodo == 'meses' else 1
        r = (rec.tasa_descuento / 100.0 / divisor) if rec.tasa_descuento else (0.08 / divisor)
        unidad = 'meses' if rec.tipo_periodo == 'meses' else 'años'

        # VAN
        van = sum(cf / (1 + r) ** t for t, cf in enumerate(flujos))

        # TIR (bisección numérica)
        tir_val = self._calc_irr(flujos)
        tir_pct = round(tir_val * 100, 2)

        # Payback
        acum = 0.0
        pb = float(len(flujos_raw))
        for t, cf in enumerate(flujos):
            prev = acum
            acum += cf
            if prev < 0 <= acum and t > 0:
                fraction = (-prev / cf) if cf else 0
                pb = (t - 1) + fraction
                break

        # Índice de rentabilidad
        pv_pos = sum(cf / (1 + r) ** t for t, cf in enumerate(flujos) if cf > 0)
        ir = round(pv_pos / rec.inversion_inicial, 2) if rec.inversion_inicial else 0.0

        # Decisión (TIR se expresa en la misma unidad que los períodos)
        tasa = rec.tasa_descuento
        tasa_ref = tasa / divisor  # tasa por período para comparar con TIR por período
        if van > 0 and tir_pct > tasa_ref:
            decision = f'VIABLE — VAN positivo ({van:,.0f}€), TIR {tir_pct:.1f}% por período > tasa {tasa_ref:.2f}%'
            color = 'green'
        elif van > 0:
            decision = f'ACEPTABLE — VAN positivo pero TIR ({tir_pct:.1f}%) por debajo de la tasa objetivo'
            color = 'yellow'
        elif van > -rec.inversion_inicial * 0.1:
            decision = 'MARGINAL — VAN negativo pero próximo a cero. Revisar hipótesis'
            color = 'yellow'
        else:
            decision = f'NO VIABLE — VAN negativo ({van:,.0f}€). La inversión destruye valor'
            color = 'red'

        fa = sum(flujos)
        return {
            'van': round(van, 2),
            'tir': tir_pct,
            'payback_anos': round(pb, 1),
            'indice_rentabilidad': ir,
            'beneficio_total': round(fa, 2),
            'flujo_acumulado': round(fa, 2),
            'decision': decision,
            'decision_color': color,
        }

    def _calc_irr(self, flujos):
        def npv(r):
            try:
                return sum(cf / (1 + r) ** t for t, cf in enumerate(flujos))
            except ZeroDivisionError:
                return float('inf')

        lo, hi = -0.9999, 100.0
        if npv(lo) * npv(hi) > 0:
            return 0.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if abs(npv(mid)) < 0.01:
                return mid
            if npv(lo) * npv(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2.0

    def action_calcular(self):
        for rec in self:
            rec.write(rec._calcular())
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_add_years(self):
        n = len(self.cash_flow_ids)
        label = 'Mes' if self.tipo_periodo == 'meses' else 'Año'
        for i in range(1, 4):
            self.env['lira.cash.flow.line'].create({
                'wizard_id': self.id,
                'periodo': n + i,
                'descripcion': f'{label} {n + i}',
                'ingresos': 0.0,
                'gastos': 0.0,
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_nuevo_proyecto(self):
        rec = self.env['lira.van.tir'].create({
            'nombre': 'Nueva inversión',
            'inversion_inicial': 100000.0,
            'tasa_descuento': 8.0,
        })
        for i in range(1, 6):
            self.env['lira.cash.flow.line'].create({
                'wizard_id': rec.id,
                'periodo': i,
                'descripcion': f'Año {i}',
                'ingresos': 0.0,
                'gastos': 0.0,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Calculadora VAN / TIR',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def action_open(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Calculadora VAN / TIR',
            'res_model': self._name,
            'view_mode': 'list,form',
            'target': 'current',
        }
