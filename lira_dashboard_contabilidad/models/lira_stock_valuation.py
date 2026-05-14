from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta
from collections import defaultdict


class LiraStockLine(models.Model):
    _name = 'lira.stock.line'
    _description = 'Línea valoración de existencias'
    _order = 'valor_total desc'

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

    user_id         = fields.Many2one('res.users', ondelete='cascade', index=True)
    product_id      = fields.Many2one('product.product', string='Producto', index=True)
    categ_id        = fields.Many2one('product.category', string='Categoría', index=True)
    barcode         = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code    = fields.Char(related='product_id.default_code', string='Referencia interna', store=False)
    product_type    = fields.Selection(related='product_id.type', string='Tipo producto', store=False)
    product_uom_name = fields.Char(related='product_id.uom_id.name', string='Unidad de medida', store=False)
    categoria       = fields.Char('Categoría (texto)')
    qty_disponible  = fields.Float('Stock actual', digits=(16, 2))
    coste_unitario  = fields.Float('Coste unit. (€)', digits=(16, 2))
    valor_total     = fields.Float('Valor stock (€)', digits=(16, 2))
    consumo_mensual = fields.Float('Consumo/mes', digits=(16, 2))
    meses_cobertura = fields.Float('Cobertura (meses)', digits=(16, 1))
    punto_reorden   = fields.Float('Punto reorden', digits=(16, 2))
    estado          = fields.Selection([
        ('ok', 'Stock OK'), ('bajo', 'Stock bajo'),
        ('critico', 'Stock crítico'), ('exceso', 'Exceso de stock'),
    ], string='Estado', index=True)


class LiraStockValuation(models.TransientModel):
    _name = 'lira.stock.valuation'
    _description = 'Valoración de existencias y aprovisionamientos'
    _rec_name = 'display_title'

    display_title        = fields.Char(default='Existencias y Aprovisionamientos', readonly=True)
    meses_consumo        = fields.Integer('Meses para calcular consumo', default=3)
    meses_cobertura_min  = fields.Float('Cobertura mínima (meses)', default=1.0)
    meses_cobertura_max  = fields.Float('Alerta exceso (meses)', default=6.0)
    valor_total_stock    = fields.Float('Valor total inventario (€)', readonly=True)
    productos_ok         = fields.Integer(readonly=True)
    productos_bajo       = fields.Integer(readonly=True)
    productos_critico    = fields.Integer(readonly=True)
    productos_exceso     = fields.Integer(readonly=True)
    pedidos_urgentes     = fields.Integer('Pedidos urgentes recomendados', readonly=True)

    def _build_data(self):
        rec = self
        today = date.today()
        meses = max(rec.meses_consumo, 1)
        fecha_ini = today - relativedelta(months=meses)
        moves = self.env['stock.move'].search([
            ('state', '=', 'done'), ('date', '>=', str(fecha_ini)), ('date', '<=', str(today)),
            ('location_dest_id.usage', '=', 'customer'), ('company_id', '=', self.env.company.id),
        ])
        consumo = defaultdict(float)
        for m in moves:
            consumo[m.product_id.id] += m.product_qty
        quants = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'), ('company_id', '=', self.env.company.id),
        ])
        stock_by_product = defaultdict(float)
        for q in quants:
            stock_by_product[q.product_id.id] += q.quantity
        all_pids = set(stock_by_product.keys()) | set(consumo.keys())
        lines_data = []
        for pid in all_pids:
            prod = self.env['product.product'].browse(pid)
            if not prod.exists(): continue
            qty = stock_by_product.get(pid, 0.0)
            coste = prod.standard_price
            valor = qty * coste
            cons_m = consumo.get(pid, 0.0) / meses
            cobertura = round(qty / cons_m, 1) if cons_m > 0 else 99.0
            punto_r = cons_m * rec.meses_cobertura_min * 1.5
            if qty <= 0:
                estado = 'critico'
            elif cobertura < rec.meses_cobertura_min:
                estado = 'bajo'
            elif cobertura > rec.meses_cobertura_max:
                estado = 'exceso'
            else:
                estado = 'ok'
            lines_data.append({
                'product_id': pid, 'categ_id': prod.categ_id.id or False,
                'categoria': prod.categ_id.name or '—',
                'qty_disponible': qty, 'coste_unitario': coste, 'valor_total': valor,
                'consumo_mensual': cons_m, 'meses_cobertura': cobertura,
                'punto_reorden': punto_r, 'estado': estado,
            })
        lines_data.sort(key=lambda x: -x['valor_total'])
        kpis = {
            'valor_total_stock': sum(d['valor_total'] for d in lines_data),
            'productos_ok':      sum(1 for d in lines_data if d['estado'] == 'ok'),
            'productos_bajo':    sum(1 for d in lines_data if d['estado'] == 'bajo'),
            'productos_critico': sum(1 for d in lines_data if d['estado'] == 'critico'),
            'productos_exceso':  sum(1 for d in lines_data if d['estado'] == 'exceso'),
        }
        kpis['pedidos_urgentes'] = kpis['productos_bajo'] + kpis['productos_critico']
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.stock.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_stock_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_stock_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Existencias — detalle',
            'res_model': 'lira.stock.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    @api.onchange('meses_consumo', 'meses_cobertura_min', 'meses_cobertura_max')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def action_refresh(self):
        self._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def action_open(self):
        rec = self.create({})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Valoración de Existencias',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
