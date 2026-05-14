from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


# ── IVA — LIQUIDACIÓN MODELO 303 ─────────────────────────────────────────────

class LiraVatLine(models.TransientModel):
    _name = 'lira.vat.line'
    _description = 'Línea liquidación IVA por mes'

    def action_open_source(self):
        """Abre facturas del mes (ventas + compras) en Contabilidad."""
        self.ensure_one()
        from datetime import datetime
        try:
            dt_ini = datetime.strptime(self.mes + '-01', '%Y-%m-%d').date()
        except Exception:
            return False
        from dateutil.relativedelta import relativedelta
        dt_fin = dt_ini + relativedelta(months=1) - relativedelta(days=1)
        return {
            'type': 'ir.actions.act_window',
            'name': f'Facturas — {self.mes}',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', 'in', ['out_invoice','out_refund','in_invoice','in_refund']),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', dt_ini),
                ('invoice_date', '<=', dt_fin),
            ],
            'target': 'current',
        }

    wizard_id         = fields.Many2one('lira.vat.settlement', ondelete='cascade')
    mes               = fields.Char('Mes', readonly=True)
    base_repercutida  = fields.Float('Base ventas (€)', digits=(16, 2), readonly=True,
        help='Base imponible de las ventas del mes. Fuente: tax_base_amount de las líneas de cuentas 477x')
    cuota_repercutida = fields.Float('IVA repercutido (€)', digits=(16, 2), readonly=True,
        help='Cuota de IVA cobrada a clientes. Fuente: saldo acreedor neto de cuentas 477x')
    base_deducible    = fields.Float('Base compras (€)', digits=(16, 2), readonly=True,
        help='Base imponible de las compras deducibles del mes. Fuente: tax_base_amount de las líneas de cuentas 472x')
    cuota_deducible   = fields.Float('IVA deducible (€)', digits=(16, 2), readonly=True,
        help='Cuota de IVA pagada a proveedores y deducible. Fuente: saldo deudor neto de cuentas 472x')
    resultado         = fields.Float('Resultado (€)', digits=(16, 2), readonly=True,
        help='Resultado del período: IVA repercutido − IVA deducible. Positivo = a ingresar a Hacienda. Negativo = a devolver o compensar')


class LiraVatSettlement(models.TransientModel):
    _name = 'lira.vat.settlement'
    _description = 'Liquidación IVA (Modelo 303)'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Liquidación IVA — Modelo 303', readonly=True)

    date_from = fields.Date('Desde',
        default=lambda s: date.today().replace(month=1, day=1),
        help='Inicio del período a analizar. Por defecto: 1 de enero del año en curso')
    date_to   = fields.Date('Hasta',
        default=fields.Date.today,
        help='Fin del período a analizar. Por defecto: hoy')

    line_ids          = fields.One2many('lira.vat.line', 'wizard_id', string='Detalle mensual')
    tiene_ceros       = fields.Boolean(readonly=True)

    total_base_rep    = fields.Float('Base imponible ventas (€)', readonly=True, digits=(16, 2),
        help='Suma de bases imponibles de todas las ventas del período')
    total_cuota_rep   = fields.Float('IVA repercutido total (€)', readonly=True, digits=(16, 2),
        help='Total IVA cobrado a clientes en el período')
    total_base_ded    = fields.Float('Base imponible compras (€)', readonly=True, digits=(16, 2),
        help='Suma de bases imponibles de todas las compras deducibles del período')
    total_cuota_ded   = fields.Float('IVA deducible total (€)', readonly=True, digits=(16, 2),
        help='Total IVA pagado a proveedores y deducible en el período')
    resultado_total   = fields.Float('Resultado acumulado (€)', readonly=True, digits=(16, 2),
        help='Resultado neto del período: IVA repercutido − IVA deducible acumulado. Positivo = importe a ingresar a Hacienda')
    ultimo_trimestre  = fields.Float('Resultado último trimestre (€)', readonly=True, digits=(16, 2),
        help='Resultado neto del último trimestre completo cerrado. Orientativo para el próximo pago trimestral del Modelo 303')

    def _bal(self, prefix, date_ini, date_fin):
        lines = self.env['account.move.line'].search([
            ('account_id.code', '=like', prefix + '%'),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_ini),
            ('date', '<=', date_fin),
            ('company_id', '=', self.env.company.id),
        ])
        return lines

    def _do_compute(self):
        for rec in self:
            if not rec.date_from or not rec.date_to:
                continue

            d_from = rec.date_from if isinstance(rec.date_from, date) else rec.date_from
            d_to   = rec.date_to   if isinstance(rec.date_to,   date) else rec.date_to

            # iterar mes a mes dentro del rango
            cur = d_from.replace(day=1)
            end = d_to.replace(day=1)
            lines_data = []

            while cur <= end:
                mes_ini = cur
                mes_fin = cur + relativedelta(months=1) - relativedelta(days=1)
                mes_fin = min(mes_fin, d_to)

                # 477x — IVA repercutido
                aml_rep = rec._bal('477', mes_ini, mes_fin)
                cuota_rep = round(sum(l.credit - l.debit for l in aml_rep), 2)
                base_rep  = round(sum(abs(l.tax_base_amount) for l in aml_rep if l.tax_base_amount), 2)

                # 472x — IVA soportado
                aml_ded = rec._bal('472', mes_ini, mes_fin)
                cuota_ded = round(sum(l.debit - l.credit for l in aml_ded), 2)
                base_ded  = round(sum(abs(l.tax_base_amount) for l in aml_ded if l.tax_base_amount), 2)

                resultado = round(cuota_rep - cuota_ded, 2)
                lines_data.append({
                    'mes':               cur.strftime('%b %Y'),
                    'base_repercutida':  base_rep,
                    'cuota_repercutida': cuota_rep,
                    'base_deducible':    base_ded,
                    'cuota_deducible':   cuota_ded,
                    'resultado':         resultado,
                })
                cur += relativedelta(months=1)

            rec.line_ids = [(5,)] + [(0, 0, d) for d in lines_data]
            rec.tiene_ceros = any(
                d['cuota_repercutida'] == 0 and d['cuota_deducible'] == 0
                for d in lines_data
            )
            rec.total_base_rep  = round(sum(d['base_repercutida']  for d in lines_data), 2)
            rec.total_cuota_rep = round(sum(d['cuota_repercutida'] for d in lines_data), 2)
            rec.total_base_ded  = round(sum(d['base_deducible']    for d in lines_data), 2)
            rec.total_cuota_ded = round(sum(d['cuota_deducible']   for d in lines_data), 2)
            rec.resultado_total = round(rec.total_cuota_rep - rec.total_cuota_ded, 2)

            # último trimestre cerrado
            today = date.today()
            q = (today.month - 1) // 3
            if q == 0:
                q_ini = date(today.year - 1, 10, 1)
                q_fin = date(today.year - 1, 12, 31)
            else:
                q_ini = date(today.year, (q - 1) * 3 + 1, 1)
                q_fin = date(today.year, q * 3, 1) + relativedelta(months=1) - relativedelta(days=1)

            rep_q = rec._bal('477', q_ini, q_fin)
            ded_q = rec._bal('472', q_ini, q_fin)
            rep_q_total = round(sum(l.credit - l.debit for l in rep_q), 2)
            ded_q_total = round(sum(l.debit - l.credit for l in ded_q), 2)
            rec.ultimo_trimestre = round(rep_q_total - ded_q_total, 2)

    @api.onchange('date_from', 'date_to')
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
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_vat_line_list2', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_vat_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Liquidación IVA — detalle mensual',
            'res_model': 'lira.vat.line',
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
            'name': 'Liquidación IVA — Modelo 303',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }


# ── IRPF — SALDO CUENTA 4751 ──────────────────────────────────────────────────

class LiraIrpfLine(models.TransientModel):
    _name = 'lira.irpf.line'
    _description = 'Movimientos mensuales cuenta 4751 (IRPF)'

    def action_open_source(self):
        """Abre apuntes contables de la cuenta 4751 del mes."""
        self.ensure_one()
        from datetime import datetime
        try:
            dt_ini = datetime.strptime(self.mes + '-01', '%Y-%m-%d').date()
        except Exception:
            return False
        from dateutil.relativedelta import relativedelta
        dt_fin = dt_ini + relativedelta(months=1) - relativedelta(days=1)
        return {
            'type': 'ir.actions.act_window',
            'name': f'Apuntes cuenta 4751 — {self.mes}',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('account_id.code', '=like', '4751%'),
                ('parent_state', '=', 'posted'),
                ('date', '>=', dt_ini),
                ('date', '<=', dt_fin),
            ],
            'target': 'current',
        }

    wizard_id  = fields.Many2one('lira.irpf', ondelete='cascade')
    mes        = fields.Char('Mes', readonly=True)
    retenido   = fields.Float('Retenido (€)', digits=(16, 2), readonly=True,
        help='IRPF acumulado en el mes: suma de los abonos (créditos) en cuenta 4751 — retenciones practicadas sobre nóminas, alquileres y profesionales')
    ingresado  = fields.Float('Ingresado a Hacienda (€)', digits=(16, 2), readonly=True,
        help='Importes pagados a Hacienda en el mes: suma de los cargos (débitos) en cuenta 4751')
    saldo_mes  = fields.Float('Saldo del mes (€)', digits=(16, 2), readonly=True,
        help='Diferencia entre retenido e ingresado en el mes. Positivo = pendiente de pago acumulado en el mes')


class LiraIrpf(models.TransientModel):
    _name = 'lira.irpf'
    _description = 'IRPF a ingresar — cuenta 4751'
    _rec_name = 'display_title'

    display_title = fields.Char(default='IRPF a Ingresar — Cuenta 4751', readonly=True)

    meses         = fields.Integer('Meses a mostrar', default=12,
        help='Número de meses pasados que se muestran en el detalle de movimientos')

    line_ids      = fields.One2many('lira.irpf.line', 'wizard_id', string='Movimientos mensuales')
    tiene_ceros   = fields.Boolean(readonly=True)

    saldo_actual  = fields.Float('Saldo pendiente de ingresar (€)', readonly=True, digits=(16, 2),
        help='Saldo acreedor total de la cuenta 4751: importe de IRPF retenido que aún no se ha ingresado a Hacienda. Un saldo positivo significa que se debe pagar ese importe')
    total_retenido_periodo  = fields.Float('Total retenido en el período (€)', readonly=True, digits=(16, 2),
        help='Suma de retenciones practicadas en los meses mostrados')
    total_ingresado_periodo = fields.Float('Total ingresado en el período (€)', readonly=True, digits=(16, 2),
        help='Suma de pagos realizados a Hacienda en los meses mostrados')

    def _do_compute(self):
        for rec in self:
            cid = self.env.company.id
            today = date.today()
            n = max(rec.meses, 1)

            # saldo total actual de cuenta 4751 (acreedor = crédito - débito)
            all_lines = self.env['account.move.line'].search([
                ('account_id.code', '=like', '4751%'),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', cid),
            ])
            rec.saldo_actual = round(sum(l.credit - l.debit for l in all_lines), 2)

            # desglose mensual
            lines_data = []
            for i in range(n - 1, -1, -1):
                mes_ini = (today - relativedelta(months=i)).replace(day=1)
                mes_fin = mes_ini + relativedelta(months=1) - relativedelta(days=1)

                month_lines = self.env['account.move.line'].search([
                    ('account_id.code', '=like', '4751%'),
                    ('move_id.state', '=', 'posted'),
                    ('date', '>=', mes_ini),
                    ('date', '<=', mes_fin),
                    ('company_id', '=', cid),
                ])
                retenido  = round(sum(l.credit for l in month_lines), 2)
                ingresado = round(sum(l.debit  for l in month_lines), 2)
                saldo_mes = round(retenido - ingresado, 2)
                lines_data.append({
                    'mes':       mes_ini.strftime('%b %Y'),
                    'retenido':  retenido,
                    'ingresado': ingresado,
                    'saldo_mes': saldo_mes,
                })

            rec.line_ids = [(5,)] + [(0, 0, d) for d in lines_data]
            rec.tiene_ceros = all(
                d['retenido'] == 0 and d['ingresado'] == 0
                for d in lines_data
            )
            rec.total_retenido_periodo  = round(sum(d['retenido']  for d in lines_data), 2)
            rec.total_ingresado_periodo = round(sum(d['ingresado'] for d in lines_data), 2)

    @api.onchange('meses')
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
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_irpf_line_list2', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_irpf_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'IRPF — movimientos mensuales',
            'res_model': 'lira.irpf.line',
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
            'name': 'IRPF a Ingresar — Cuenta 4751',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
