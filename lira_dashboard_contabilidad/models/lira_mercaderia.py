from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta
from collections import defaultdict


class LiraMercaderiaLine(models.Model):
    _name = 'lira.mercaderia.line'
    _description = 'Línea mercadería (compra-reventa, sin fabricación)'
    _order = 'margen_euros desc'

    user_id          = fields.Many2one('res.users', ondelete='cascade', index=True)
    product_id       = fields.Many2one('product.product', string='Producto', index=True)
    barcode          = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code     = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    product_uom_name = fields.Char(related='product_id.uom_id.name', string='U. medida', store=False)
    categ_id         = fields.Many2one('product.category', string='Categoría', index=True)
    qty_vendida      = fields.Float('Uds. vendidas', digits=(16, 2))
    qty_comprada     = fields.Float('Uds. compradas', digits=(16, 2))
    qty_stock        = fields.Float('Uds. en stock', digits=(16, 2))
    ingreso_ventas   = fields.Float('Ingresos por ventas (€)', digits=(16, 2))
    coste_compra     = fields.Float('Coste de compra (€)', digits=(16, 2))
    margen_euros     = fields.Float('Margen (€)', digits=(16, 2))
    margen_pct       = fields.Float('Margen (%)', digits=(16, 1))
    rotacion_dias    = fields.Float('Rotación (días)', digits=(16, 1))

    def action_open_source(self):
        """Abre la ficha del producto."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ficha del producto',
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class LiraMercaderia(models.TransientModel):
    _name = 'lira.mercaderia'
    _description = 'Mercadería (compra-reventa) — productos sin fabricación'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Mercadería (Compra-Reventa)', readonly=True)

    date_from = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to   = fields.Date('Hasta', default=fields.Date.today)

    num_productos       = fields.Integer('Productos sin fabricación',   readonly=True)
    total_ingresos      = fields.Float('Ingresos por ventas (€)',       readonly=True)
    total_coste         = fields.Float('Coste de compra (€)',           readonly=True)
    total_margen        = fields.Float('Margen bruto (€)',              readonly=True)
    margen_medio_pct    = fields.Float('Margen medio (%)',              readonly=True)
    valor_stock_actual  = fields.Float('Valor stock actual (€)',        readonly=True)
    total_uds_vendidas  = fields.Float('Uds. vendidas',                 readonly=True)
    total_uds_compradas = fields.Float('Uds. compradas',                readonly=True)

    # ───────────────────────────────────────────────────────────────────
    def _is_manufactured(self, product):
        """Un producto es fabricado si tiene una lista de materiales (BoM) activa."""
        return bool(self.env['mrp.bom'].search_count([
            '|', ('product_id', '=', product.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ]))

    def _build_data(self):
        df = self.date_from or date.today().replace(month=1, day=1)
        dt = self.date_to   or date.today()
        cid = self.env.company.id
        periodo_dias = max(1, (dt - df).days + 1)

        # 1) Productos candidatos: almacenables/consumibles, sin BoM
        products = self.env['product.product'].search([
            ('type', 'in', ['product','consu']),
            ('active', '=', True),
            ('company_id', 'in', [False, cid]),
        ])
        productos_sin_fab = products.filtered(lambda p: not self._is_manufactured(p))

        # 2) Ventas y compras del periodo
        sol_lines = self.env['sale.order.line'].search([
            ('order_id.state', 'in', ['sale','done']),
            ('order_id.company_id', '=', cid),
            ('order_id.date_order', '>=', df),
            ('order_id.date_order', '<=', str(dt) + ' 23:59:59'),
            ('product_id', 'in', productos_sin_fab.ids),
        ])
        pol_lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ['purchase','done']),
            ('order_id.company_id', '=', cid),
            ('order_id.date_order', '>=', df),
            ('order_id.date_order', '<=', str(dt) + ' 23:59:59'),
            ('product_id', 'in', productos_sin_fab.ids),
        ])

        data_prod = defaultdict(lambda: {'qty_v': 0.0, 'qty_c': 0.0, 'ing': 0.0, 'cost': 0.0})
        for l in sol_lines:
            data_prod[l.product_id.id]['qty_v'] += l.product_uom_qty
            data_prod[l.product_id.id]['ing'] += l.price_subtotal
        for l in pol_lines:
            data_prod[l.product_id.id]['qty_c'] += l.product_qty
            data_prod[l.product_id.id]['cost'] += l.price_subtotal

        # 3) Stock actual
        quants = self.env['stock.quant'].read_group(
            [('location_id.usage', '=', 'internal'), ('company_id', '=', cid),
             ('product_id', 'in', productos_sin_fab.ids)],
            ['product_id', 'quantity:sum'], ['product_id'],
        )
        stock_map = {q['product_id'][0]: q['quantity'] for q in quants if q.get('product_id')}

        lines_data = []
        tot_ing = tot_cost = tot_vuds = tot_cuds = tot_stock_val = 0.0
        for prod in productos_sin_fab:
            d = data_prod.get(prod.id, {'qty_v': 0.0, 'qty_c': 0.0, 'ing': 0.0, 'cost': 0.0})
            qty_stock = stock_map.get(prod.id, 0.0) or 0.0
            # Si no tiene nada de actividad ni stock, lo saltamos
            if d['qty_v'] == 0 and d['qty_c'] == 0 and qty_stock == 0:
                continue

            ing = d['ing']
            # Coste real desde compras del periodo; si no hay, usar standard_price × uds vendidas
            if d['qty_c'] > 0 and d['qty_v'] > 0:
                coste_unit = d['cost'] / d['qty_c'] if d['qty_c'] else prod.standard_price
                coste = coste_unit * d['qty_v']
            else:
                coste = (prod.standard_price or 0.0) * d['qty_v']

            margen = ing - coste
            margen_pct = round(margen / ing * 100, 1) if ing > 0 else 0.0
            # Rotación: días que tarda en agotarse el stock al ritmo de ventas del periodo
            ritmo_diario = d['qty_v'] / periodo_dias if periodo_dias else 0.0
            rotacion = round(qty_stock / ritmo_diario, 1) if ritmo_diario > 0 else 0.0

            valor_stock = qty_stock * (prod.standard_price or 0.0)
            tot_ing += ing
            tot_cost += coste
            tot_vuds += d['qty_v']
            tot_cuds += d['qty_c']
            tot_stock_val += valor_stock

            lines_data.append({
                'product_id':    prod.id,
                'categ_id':      prod.categ_id.id or False,
                'qty_vendida':   round(d['qty_v'], 2),
                'qty_comprada':  round(d['qty_c'], 2),
                'qty_stock':     round(qty_stock, 2),
                'ingreso_ventas': round(ing, 2),
                'coste_compra':  round(coste, 2),
                'margen_euros':  round(margen, 2),
                'margen_pct':    margen_pct,
                'rotacion_dias': rotacion,
            })

        lines_data.sort(key=lambda x: -x['margen_euros'])
        kpis = {
            'num_productos':       len(lines_data),
            'total_ingresos':      round(tot_ing, 2),
            'total_coste':         round(tot_cost, 2),
            'total_margen':        round(tot_ing - tot_cost, 2),
            'margen_medio_pct':    round((tot_ing - tot_cost) / tot_ing * 100, 1) if tot_ing > 0 else 0.0,
            'valor_stock_actual':  round(tot_stock_val, 2),
            'total_uds_vendidas':  round(tot_vuds, 2),
            'total_uds_compradas': round(tot_cuds, 2),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.mercaderia.line']
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
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_mercaderia_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_mercaderia_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Mercadería — detalle por producto',
            'res_model': 'lira.mercaderia.line', 'view_mode': 'list',
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
        rec = self.create({'date_from': date.today().replace(month=1, day=1), 'date_to': date.today()})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Mercadería (Compra-Reventa)',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
