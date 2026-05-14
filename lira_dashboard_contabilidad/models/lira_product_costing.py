from odoo import models, fields, api
from datetime import date
from collections import defaultdict


class LiraProductCostingLine(models.Model):
    _name = 'lira.product.costing.line'
    _description = 'Línea escandallo de costes'
    _order = 'margen_pct asc'

    def action_open_source(self):
        """Abre la ficha del producto."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Producto',
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    user_id        = fields.Many2one('res.users', ondelete='cascade', index=True)
    rank           = fields.Integer('Pos.')
    product_id     = fields.Many2one('product.product', string='Producto', index=True)
    barcode        = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code   = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    product_uom_name = fields.Char(related='product_id.uom_id.name', string='U. medida', store=False)
    categ_id       = fields.Many2one('product.category', string='Categoría', index=True)
    categoria      = fields.Char('Categoría (texto)')
    uds_vendidas   = fields.Float('Uds. vendidas', digits=(16, 2))
    pvp_medio      = fields.Float('PVP medio (€)', digits=(16, 2))
    coste_unitario = fields.Float('Coste unit. (€)', digits=(16, 2))
    margen_unitario = fields.Float('Margen unit. (€)', digits=(16, 2))
    margen_pct     = fields.Float('Margen (%)', digits=(16, 1))
    total_ventas   = fields.Float('Total ventas (€)', digits=(16, 2))
    total_margen   = fields.Float('Total margen (€)', digits=(16, 2))
    alerta         = fields.Selection([
        ('ok', 'OK'), ('medio', 'Margen bajo'), ('critico', 'Margen crítico'),
    ], string='Alerta', index=True)


class LiraProductCosting(models.TransientModel):
    _name = 'lira.product.costing'
    _description = 'Escandallo de costes y márgenes por producto'
    _rec_name = 'display_title'

    display_title    = fields.Char(default='Escandallo de Costes', readonly=True)
    date_from        = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to          = fields.Date('Hasta', default=fields.Date.today)
    umbral_bajo      = fields.Float('Umbral margen bajo (%)', default=20.0)
    umbral_critico   = fields.Float('Umbral margen crítico (%)', default=5.0)
    total_ventas     = fields.Float(readonly=True)
    total_coste      = fields.Float(readonly=True)
    total_margen     = fields.Float(readonly=True)
    margen_global    = fields.Float(readonly=True)
    productos_ok     = fields.Integer(readonly=True)
    productos_bajo   = fields.Integer(readonly=True)
    productos_critico = fields.Integer(readonly=True)

    def _build_data(self):
        rec = self
        df, dt, cid = rec.date_from or date.today().replace(month=1, day=1), rec.date_to or date.today(), self.env.company.id
        inv_lines = self.env['account.move.line'].search([
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', df),
            ('move_id.invoice_date', '<=', dt),
            ('move_id.company_id', '=', cid),
            ('display_type', '=', 'product'),
            ('product_id', '!=', False),
        ])
        groups = defaultdict(lambda: {'qty': 0.0, 'importe': 0.0, 'product': None})
        for l in inv_lines:
            sign = -1 if l.move_id.move_type == 'out_refund' else 1
            groups[l.product_id.id]['qty'] += sign * l.quantity
            groups[l.product_id.id]['importe'] += sign * l.price_subtotal
            groups[l.product_id.id]['product'] = l.product_id
        vendor_lines = self.env['account.move.line'].search([
            ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
            ('move_id.state', '=', 'posted'),
            ('move_id.company_id', '=', cid),
            ('display_type', '=', 'product'),
            ('product_id', 'in', list(groups.keys())),
            ('quantity', '>', 0),
        ])
        vendor_totals = defaultdict(lambda: {'val': 0.0, 'qty': 0.0})
        for vl in vendor_lines:
            sign = -1 if vl.move_id.move_type == 'in_refund' else 1
            vendor_totals[vl.product_id.id]['val'] += sign * vl.price_subtotal
            vendor_totals[vl.product_id.id]['qty'] += sign * vl.quantity
        lines_data = []
        for pid, g in groups.items():
            prod, qty, vtas = g['product'], g['qty'], g['importe']
            if qty <= 0 or vtas <= 0:
                continue
            pvp_m = round(vtas / qty, 4)
            coste_u = prod.standard_price
            if coste_u == 0:
                vt = vendor_totals.get(pid)
                if vt and vt['qty'] > 0:
                    coste_u = vt['val'] / vt['qty']
            margen_u = pvp_m - coste_u
            total_c = coste_u * qty
            total_m = vtas - total_c
            pct = round(total_m / vtas * 100, 1) if vtas else 0.0
            alerta = 'critico' if pct < rec.umbral_critico else ('medio' if pct < rec.umbral_bajo else 'ok')
            lines_data.append({
                'product_id': pid, 'categ_id': prod.categ_id.id or False,
                'categoria': prod.categ_id.name or '—',
                'uds_vendidas': round(qty, 2), 'pvp_medio': round(pvp_m, 2),
                'coste_unitario': round(coste_u, 2), 'margen_unitario': round(margen_u, 2),
                'margen_pct': pct, 'total_ventas': round(vtas, 2),
                'total_margen': round(total_m, 2), 'alerta': alerta,
            })
        lines_data.sort(key=lambda x: x['margen_pct'])
        tv = sum(d['total_ventas'] for d in lines_data)
        tc = sum(d['coste_unitario'] * d['uds_vendidas'] for d in lines_data)
        tm = tv - tc
        kpis = {
            'total_ventas': tv, 'total_coste': tc, 'total_margen': tm,
            'margen_global': round(tm / tv * 100, 1) if tv else 0.0,
            'productos_ok': sum(1 for d in lines_data if d['alerta'] == 'ok'),
            'productos_bajo': sum(1 for d in lines_data if d['alerta'] == 'medio'),
            'productos_critico': sum(1 for d in lines_data if d['alerta'] == 'critico'),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.product.costing.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for i, d in enumerate(lines_data, 1):
                Line.create({**d, 'rank': i, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_product_costing_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_product_costing_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Escandallo de costes — detalle',
            'res_model': 'lira.product.costing.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    @api.onchange('date_from', 'date_to', 'umbral_bajo', 'umbral_critico')
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
        return {'type': 'ir.actions.act_window', 'name': 'Escandallo de Costes',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
