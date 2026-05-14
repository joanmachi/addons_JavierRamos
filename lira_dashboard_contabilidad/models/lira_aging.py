from odoo import models, fields, api
from datetime import date
from collections import defaultdict


class LiraAgingLine(models.Model):
    _name = 'lira.aging.line'
    _description = 'Línea antigüedad de saldos'
    _order = 'total desc'

    def action_open_source(self):
        """Abre las facturas pendientes del cliente en Odoo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Facturas pendientes — {self.partner_id.name}',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('partner_id.commercial_partner_id', '=', self.partner_id.id),
            ],
            'target': 'current',
        }

    user_id      = fields.Many2one('res.users', ondelete='cascade', index=True)
    rank         = fields.Integer('Pos.')
    partner_id   = fields.Many2one('res.partner', string='Cliente', index=True)
    partner_vat  = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    partner_ref  = fields.Char(related='partner_id.ref', string='Ref. cliente', store=False)
    partner_email = fields.Char(related='partner_id.email', string='Email', store=False)
    partner_phone = fields.Char(related='partner_id.phone', string='Teléfono', store=False)
    corriente    = fields.Float('Corriente (€)', digits=(16, 2))
    tramo_30     = fields.Float('1–30 días (€)', digits=(16, 2))
    tramo_60     = fields.Float('31–60 días (€)', digits=(16, 2))
    tramo_90     = fields.Float('61–90 días (€)', digits=(16, 2))
    tramo_mas    = fields.Float('+90 días (€)', digits=(16, 2))
    total        = fields.Float('Total pendiente (€)', digits=(16, 2))
    num_facturas = fields.Integer('Facturas')
    dias_max     = fields.Integer('Días máx. vencido')


class LiraAging(models.TransientModel):
    _name = 'lira.aging'
    _description = 'Antigüedad de saldos de clientes'
    _rec_name = 'display_title'

    display_title     = fields.Char(default='Antigüedad de Saldos', readonly=True)
    total_pendiente   = fields.Float('Total pendiente (€)', readonly=True)
    total_vencido     = fields.Float('Total vencido (€)', readonly=True)
    importe_corriente = fields.Float('Corriente (€)', readonly=True)
    importe_critico   = fields.Float('+90 días (€)', readonly=True)
    clientes_vencidos = fields.Integer('Clientes con deuda vencida', readonly=True)

    def _build_data(self):
        """Calcula y devuelve (lines_data, kpis) sin tocar la BD."""
        today = date.today()
        facturas = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('company_id', '=', self.env.company.id),
        ])
        groups = defaultdict(lambda: {
            'partner': None,
            'corriente': 0.0, 'tramo_30': 0.0, 'tramo_60': 0.0,
            'tramo_90': 0.0, 'tramo_mas': 0.0,
            'facturas': 0, 'dias_max': 0,
        })
        for inv in facturas:
            cp = inv.partner_id.commercial_partner_id
            pid = cp.id
            groups[pid]['partner'] = cp
            groups[pid]['facturas'] += 1
            residual = inv.amount_residual
            due = inv.invoice_date_due
            dias = (today - due).days if due else 0
            if dias > groups[pid]['dias_max']:
                groups[pid]['dias_max'] = dias
            if dias <= 0:
                groups[pid]['corriente'] += residual
            elif dias <= 30:
                groups[pid]['tramo_30'] += residual
            elif dias <= 60:
                groups[pid]['tramo_60'] += residual
            elif dias <= 90:
                groups[pid]['tramo_90'] += residual
            else:
                groups[pid]['tramo_mas'] += residual

        lines_data = []
        for pid, g in groups.items():
            if not g['partner']:
                continue
            total = (g['corriente'] + g['tramo_30'] + g['tramo_60']
                     + g['tramo_90'] + g['tramo_mas'])
            lines_data.append({
                'partner_id':   pid,
                'corriente':    round(g['corriente'], 2),
                'tramo_30':     round(g['tramo_30'], 2),
                'tramo_60':     round(g['tramo_60'], 2),
                'tramo_90':     round(g['tramo_90'], 2),
                'tramo_mas':    round(g['tramo_mas'], 2),
                'total':        round(total, 2),
                'num_facturas': g['facturas'],
                'dias_max':     g['dias_max'],
            })
        lines_data.sort(key=lambda x: -x['total'])
        kpis = {
            'total_pendiente':   round(sum(d['total'] for d in lines_data), 2),
            'importe_corriente': round(sum(d['corriente'] for d in lines_data), 2),
            'total_vencido':     round(sum(d['tramo_30'] + d['tramo_60'] + d['tramo_90'] + d['tramo_mas'] for d in lines_data), 2),
            'importe_critico':   round(sum(d['tramo_mas'] for d in lines_data), 2),
            'clientes_vencidos': sum(1 for d in lines_data if d['tramo_30'] + d['tramo_60'] + d['tramo_90'] + d['tramo_mas'] > 0),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.aging.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for i, d in enumerate(lines_data, 1):
                Line.create({**d, 'rank': i, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_aging_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_aging_line_search', raise_if_not_found=False)
        action = {
            'type':      'ir.actions.act_window',
            'name':      'Antigüedad de saldos — detalle',
            'res_model': 'lira.aging.line',
            'view_mode': 'list',
            'domain':    [('user_id', '=', self.env.user.id)],
            'context':   {'create': False, 'delete': False},
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
        rec = self.create({})
        rec._compute_kpis_only()
        return {
            'type': 'ir.actions.act_window', 'name': 'Antigüedad de Saldos',
            'res_model': self._name, 'res_id': rec.id,
            'view_mode': 'form', 'target': 'current',
        }
