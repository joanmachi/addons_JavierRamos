from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


class LiraModelo111Line(models.Model):
    _name = 'lira.modelo.111.line'
    _description = 'Línea Modelo 111 — Retenciones IRPF practicadas'
    _order = 'trimestre, importe_retenido desc'

    user_id      = fields.Many2one('res.users', ondelete='cascade', index=True)
    partner_id   = fields.Many2one('res.partner', string='Perceptor', index=True)
    partner_vat  = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    concepto     = fields.Selection([
        ('trabajo',      'Rendimientos del trabajo'),
        ('profesional',  'Actividades profesionales'),
        ('alquiler',     'Alquileres (modelo 115)'),
        ('otros',        'Otros (premios, etc.)'),
    ], string='Concepto', index=True)
    move_id      = fields.Many2one('account.move', string='Factura/apunte')
    referencia   = fields.Char('Referencia')
    fecha        = fields.Date('Fecha')
    trimestre    = fields.Selection([
        ('T1', 'T1 (Ene-Mar)'), ('T2', 'T2 (Abr-Jun)'),
        ('T3', 'T3 (Jul-Sep)'), ('T4', 'T4 (Oct-Dic)'),
    ], string='Trimestre', index=True)
    ejercicio    = fields.Integer('Ejercicio', index=True)
    base         = fields.Float('Base retención (€)', digits=(16, 2))
    importe_retenido = fields.Float('Importe retenido (€)', digits=(16, 2))
    pct_retencion    = fields.Float('% retención', digits=(16, 2))

    def action_open_source(self):
        """Abre la factura o apunte de origen."""
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura/Apunte origen',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class LiraModelo111(models.TransientModel):
    _name = 'lira.modelo.111'
    _description = 'Modelo 111/115 — Retenciones IRPF'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Modelo 111/115 — Retenciones IRPF', readonly=True)

    ejercicio  = fields.Integer('Ejercicio', default=lambda s: date.today().year)
    trimestre  = fields.Selection([
        ('todos', 'Todos'),
        ('T1',    'T1 (Ene-Mar)'),
        ('T2',    'T2 (Abr-Jun)'),
        ('T3',    'T3 (Jul-Sep)'),
        ('T4',    'T4 (Oct-Dic)'),
    ], string='Trimestre', default='todos')

    # KPIs
    total_trabajo      = fields.Float('Rend. trabajo (€)',        readonly=True)
    total_profesional  = fields.Float('Profesionales (€)',        readonly=True)
    total_alquiler     = fields.Float('Alquileres (115) (€)',     readonly=True)
    total_otros        = fields.Float('Otros (€)',                readonly=True)
    total_retenido     = fields.Float('Total retenido (€)',       readonly=True)
    total_base         = fields.Float('Total base retención (€)', readonly=True)
    num_perceptores    = fields.Integer('Perceptores distintos',  readonly=True)

    # ───────────────────────────────────────────────────────────────────
    def _classify_concepto(self, aml):
        """Heurística para clasificar una retención según la contracuenta de la factura."""
        # Si la factura contiene cuentas de alquiler → alquiler (115)
        # Si es factura de profesional (tipo in_invoice con partner que tiene IRPF) → profesional
        # Si viene de nómina (cuenta 640) → trabajo
        # Si no, otros
        move = aml.move_id
        if not move:
            return 'otros'
        # Buscar contracuentas en las líneas de la misma factura
        other_codes = set()
        for ln in move.line_ids:
            if ln.account_id and ln.account_id.code:
                other_codes.add(ln.account_id.code[:3])
        if '621' in other_codes or '622' in other_codes:
            return 'alquiler'
        if '640' in other_codes or '641' in other_codes or '642' in other_codes:
            return 'trabajo'
        if move.move_type in ('in_invoice', 'in_refund'):
            return 'profesional'
        return 'otros'

    def _build_data(self):
        year = self.ejercicio or date.today().year
        cid = self.env.company.id
        dt_ini = f'{year}-01-01'
        dt_fin = f'{year}-12-31'

        # Buscar apuntes de la cuenta 4751 (HP acreedora por retenciones)
        # Los cargos en 4751 son pagos a Hacienda; los abonos son retenciones practicadas.
        AML = self.env['account.move.line']
        lines_4751 = AML.search([
            ('account_id.code', '=like', '4751%'),
            ('parent_state', '=', 'posted'),
            ('date', '>=', dt_ini),
            ('date', '<=', dt_fin),
            ('company_id', '=', cid),
        ])

        lines_data = []
        totales = {'trabajo': 0.0, 'profesional': 0.0, 'alquiler': 0.0, 'otros': 0.0}
        perceptores = set()
        total_retenido = 0.0
        total_base = 0.0

        for aml in lines_4751:
            # Solo los abonos (credit > debit) son retenciones practicadas
            retenido = (aml.credit or 0.0) - (aml.debit or 0.0)
            if retenido <= 0.001:
                continue
            concepto = self._classify_concepto(aml)
            totales[concepto] += retenido
            total_retenido += retenido

            # Fecha y trimestre
            d = aml.date
            if not d:
                continue
            m = d.month
            if m <= 3: trim = 'T1'
            elif m <= 6: trim = 'T2'
            elif m <= 9: trim = 'T3'
            else: trim = 'T4'
            if self.trimestre and self.trimestre != 'todos' and trim != self.trimestre:
                continue

            # Base imponible aproximada (buscamos en la factura la línea de base)
            base_total = 0.0
            if aml.move_id:
                for ln in aml.move_id.line_ids:
                    if ln.tax_line_id:
                        continue
                    if ln.account_id and ln.account_id.account_type in ('expense','expense_direct_cost','income'):
                        base_total += abs(ln.balance)
            total_base += base_total
            pct = round(retenido / base_total * 100, 2) if base_total > 0 else 0.0

            partner = aml.partner_id or (aml.move_id.partner_id if aml.move_id else False)
            if partner:
                perceptores.add(partner.commercial_partner_id.id)

            lines_data.append({
                'partner_id':       partner.commercial_partner_id.id if partner else False,
                'concepto':         concepto,
                'move_id':          aml.move_id.id if aml.move_id else False,
                'referencia':       aml.move_id.name if aml.move_id else aml.ref or '',
                'fecha':            d,
                'trimestre':        trim,
                'ejercicio':        year,
                'base':             round(base_total, 2),
                'importe_retenido': round(retenido, 2),
                'pct_retencion':    pct,
            })

        kpis = {
            'total_trabajo':     round(totales['trabajo'], 2),
            'total_profesional': round(totales['profesional'], 2),
            'total_alquiler':    round(totales['alquiler'], 2),
            'total_otros':       round(totales['otros'], 2),
            'total_retenido':    round(total_retenido, 2),
            'total_base':        round(total_base, 2),
            'num_perceptores':   len(perceptores),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.modelo.111.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    @api.onchange('ejercicio', 'trimestre')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_modelo_111_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_modelo_111_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Retenciones IRPF — detalle',
            'res_model': 'lira.modelo.111.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
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
        rec = self.create({'ejercicio': date.today().year})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Modelo 111/115 — Retenciones IRPF',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
