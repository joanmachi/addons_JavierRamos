from odoo import models, fields, api
from datetime import date
from collections import defaultdict


class LiraCustomerMarginLine(models.Model):
    _name = 'lira.customer.margin.line'
    _description = 'Línea margen por cliente'
    _order = 'margen_pct desc'

    def action_open_source(self):
        """Abre facturas emitidas al cliente."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Facturas — {self.partner_id.name}',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('partner_id.commercial_partner_id', '=', self.partner_id.id),
            ],
            'target': 'current',
        }

    user_id         = fields.Many2one('res.users', ondelete='cascade', index=True)
    rank            = fields.Integer('Pos.')
    partner_id      = fields.Many2one('res.partner', string='Cliente', index=True)
    partner_vat     = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city    = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    partner_ref     = fields.Char(related='partner_id.ref', string='Ref. cliente', store=False)
    partner_email   = fields.Char(related='partner_id.email', string='Email', store=False)
    partner_phone   = fields.Char(related='partner_id.phone', string='Teléfono', store=False)
    total_facturado = fields.Float('Facturado (€)', digits=(16, 2))
    coste_estimado  = fields.Float('Coste estimado (€)', digits=(16, 2))
    margen_euros    = fields.Float('Margen (€)', digits=(16, 2))
    margen_pct      = fields.Float('Margen (%)', digits=(16, 1))
    num_facturas    = fields.Integer('Facturas')
    ultimo_pedido   = fields.Date('Último pedido')


class LiraCustomerMargin(models.TransientModel):
    _name = 'lira.customer.margin'
    _description = 'Análisis de margen por cliente'
    _rec_name = 'display_title'

    display_title   = fields.Char(default='Margen por Cliente', readonly=True)
    date_from       = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to         = fields.Date('Hasta', default=fields.Date.today)
    partner_id      = fields.Many2one('res.partner', string='Filtrar por cliente',
                                      domain="[('customer_rank','>',0)]")
    total_facturado = fields.Float(readonly=True)
    total_margen    = fields.Float(readonly=True)
    media_margen    = fields.Float(readonly=True)
    mejor_cliente   = fields.Char(readonly=True)
    peor_cliente    = fields.Char(readonly=True)

    def _build_data(self):
        rec = self
        df = rec.date_from or date.today().replace(month=1, day=1)
        dt = rec.date_to   or date.today()
        domain = [
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', df),
            ('move_id.invoice_date', '<=', dt),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('product_id', '!=', False),
        ]
        if rec.partner_id:
            domain.append(('move_id.partner_id', '=', rec.partner_id.id))
        inv_lines = self.env['account.move.line'].search(domain)
        groups = defaultdict(lambda: {'partner': None, 'facturado': 0.0, 'coste': 0.0,
                                       'facturas': set(), 'fechas': []})
        for l in inv_lines:
            cp = l.move_id.partner_id.commercial_partner_id
            pid = cp.id
            groups[pid]['partner'] = cp
            groups[pid]['facturado'] += l.credit - l.debit
            groups[pid]['coste'] += l.product_id.standard_price * l.quantity
            groups[pid]['facturas'].add(l.move_id.id)
            if l.move_id.invoice_date:
                groups[pid]['fechas'].append(l.move_id.invoice_date)
        lines_data = []
        for pid, g in sorted(groups.items(), key=lambda x: -x[1]['facturado']):
            if not g['partner']:
                continue
            margen = g['facturado'] - g['coste']
            pct = round(margen / g['facturado'] * 100, 1) if g['facturado'] else 0.0
            lines_data.append({
                'partner_id': pid, 'total_facturado': g['facturado'],
                'coste_estimado': g['coste'], 'margen_euros': margen,
                'margen_pct': pct, 'num_facturas': len(g['facturas']),
                'ultimo_pedido': max(g['fechas']) if g['fechas'] else False,
            })
        tf = sum(d['total_facturado'] for d in lines_data)
        tm = sum(d['margen_euros'] for d in lines_data)
        kpis = {
            'total_facturado': tf, 'total_margen': tm,
            'media_margen': round(tm / tf * 100, 1) if tf else 0.0,
            'mejor_cliente': self.env['res.partner'].browse(lines_data[0]['partner_id']).name if lines_data else '—',
            'peor_cliente': self.env['res.partner'].browse(
                sorted(lines_data, key=lambda x: x['margen_pct'])[0]['partner_id']
            ).name if lines_data else '—',
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.customer.margin.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for i, d in enumerate(lines_data, 1):
                Line.create({**d, 'rank': i, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_customer_margin_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_customer_margin_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Margen por cliente — detalle',
            'res_model': 'lira.customer.margin.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    @api.onchange('date_from', 'date_to', 'partner_id')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def action_refresh(self):
        self._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def action_open(self):
        rec = self.create({'date_from': date.today().replace(month=1, day=1), 'date_to': date.today()})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Margen por Cliente',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
