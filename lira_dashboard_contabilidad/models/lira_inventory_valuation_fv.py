from odoo import models, fields, api
from datetime import date


class LiraInventoryValuationFvLine(models.Model):
    _name = 'lira.inventory.valuation.fv.line'
    _description = 'Línea valoración inventario fijos/variables'
    _order = 'valor_absorcion desc'

    user_id           = fields.Many2one('res.users', ondelete='cascade', index=True)
    product_id        = fields.Many2one('product.product', string='Producto', index=True)
    categ_id          = fields.Many2one('product.category', string='Categoría', index=True)
    # Campos relacionados para búsqueda/columnas opcionales
    barcode           = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code      = fields.Char(related='product_id.default_code', string='Referencia interna', store=False)
    product_type      = fields.Selection(related='product_id.type', string='Tipo producto', store=False)
    product_uom_name  = fields.Char(related='product_id.uom_id.name', string='Unidad de medida', store=False)
    qty_stock         = fields.Float('Unidades en stock', digits=(16, 3))
    coste_std_actual  = fields.Float('Precio coste actual (€/u)', digits=(16, 4))
    coste_unit_var    = fields.Float('Coste unit. variable (€/u)', digits=(16, 4))
    coste_unit_fijo   = fields.Float('Coste unit. fijo (€/u)', digits=(16, 4))
    coste_unit_abs    = fields.Float('Coste unit. absorción (€/u)', digits=(16, 4))
    valor_std_actual  = fields.Float('Valor con coste actual (€)', digits=(16, 2))
    valor_variable    = fields.Float('Valor método variable (€)', digits=(16, 2))
    valor_absorcion   = fields.Float('Valor método absorción (€)', digits=(16, 2))
    fijos_en_stock    = fields.Float('Fijos retenidos en stock (€)', digits=(16, 2))
    delta_std_abs     = fields.Float('Δ stock vs absorción (€)', digits=(16, 2))

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


class LiraInventoryValuationFv(models.TransientModel):
    _name = 'lira.inventory.valuation.fv'
    _description = 'Valoración inventario — Fijos / Variables'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Valoración Inventario (Fijos/Variables)', readonly=True)

    date_from = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to   = fields.Date('Hasta', default=fields.Date.today)

    # ─── Datos del periodo ────────────────────────────────────────────────
    total_variables_periodo  = fields.Float('Total costes variables del periodo (€)', readonly=True)
    total_fijos_periodo      = fields.Float('Total costes fijos del periodo (€)',     readonly=True)
    uds_producidas_periodo   = fields.Float('Unidades producidas en el periodo',       readonly=True)

    # ─── Costes unitarios calculados ──────────────────────────────────────
    coste_unit_variable  = fields.Float('Coste unitario variable (€/u)',  readonly=True)
    coste_unit_fijo      = fields.Float('Coste unitario fijo (€/u)',      readonly=True)
    coste_unit_absorcion = fields.Float('Coste unitario absorción (€/u)', readonly=True)

    # ─── Stock actual ─────────────────────────────────────────────────────
    uds_stock_total      = fields.Float('Unidades totales en stock',   readonly=True)
    num_productos_stock  = fields.Integer('Productos con stock',       readonly=True)

    # ─── Valoraciones ─────────────────────────────────────────────────────
    valor_stock_actual    = fields.Float('Valor actual (precio coste Odoo) (€)', readonly=True)
    valor_stock_variable  = fields.Float('Valor método variable (€)',             readonly=True)
    valor_stock_absorcion = fields.Float('Valor método absorción (€)',            readonly=True)
    diferencia_abs_var    = fields.Float('Fijos retenidos en stock (€)',          readonly=True)
    delta_stock_vs_abs    = fields.Float('Δ stock actual vs absorción (€)',       readonly=True)

    # ─── Flags ────────────────────────────────────────────────────────────
    sin_produccion = fields.Boolean(readonly=True)

    # ══════════════════════════════════════════════════════════════════════
    # Cálculos
    # ══════════════════════════════════════════════════════════════════════
    def _build_data(self):
        df = self.date_from or date.today().replace(month=1, day=1)
        dt = self.date_to   or date.today()
        cid = self.env.company.id

        # 1) Variables del periodo: solo las 7 cuentas marcadas
        AML = self.env['account.move.line']
        aml_lines = AML.search([
            ('parent_state', '=', 'posted'),
            ('date', '>=', df),
            ('date', '<=', dt),
            ('company_id', '=', cid),
            ('account_id', '!=', False),
        ])
        # Códigos variables desde la configuración (UI con fallback)
        vars_set = set(self.env['lira.variable.account'].get_variable_codes())
        tot_var = 0.0
        tot_fij = 0.0
        for ln in aml_lines:
            code = (ln.account_id.code or '')
            if not code.startswith('6'):
                continue  # solo gastos
            delta = (ln.debit or 0.0) - (ln.credit or 0.0)
            if code in vars_set:
                tot_var += delta
            else:
                tot_fij += delta

        # 2) Unidades producidas en el periodo (OFs terminadas)
        productions = self.env['mrp.production'].search([
            ('state', '=', 'done'),
            ('date_finished', '>=', df),
            ('date_finished', '<=', str(dt) + ' 23:59:59'),
            ('company_id', '=', cid),
        ])
        uds_producidas = sum(
            (p.qty_producing or p.product_qty or 0.0) for p in productions
        )
        sin_produccion = uds_producidas <= 0.001

        # 3) Costes unitarios
        if sin_produccion:
            cu_var = cu_fij = cu_abs = 0.0
        else:
            cu_var = tot_var / uds_producidas
            cu_fij = tot_fij / uds_producidas
            cu_abs = cu_var + cu_fij

        # 4) Stock actual por producto (solo productos con stock > 0)
        quants = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'),
            ('company_id', '=', cid),
        ])
        stock_by_product = {}
        for q in quants:
            if q.quantity <= 0.001 or not q.product_id:
                continue
            stock_by_product.setdefault(q.product_id.id, 0.0)
            stock_by_product[q.product_id.id] += q.quantity

        lines_data = []
        tot_uds = 0.0
        tot_val_std = tot_val_var = tot_val_abs = 0.0
        for pid, qty in stock_by_product.items():
            prod = self.env['product.product'].browse(pid)
            if not prod.exists():
                continue
            std = prod.standard_price or 0.0
            val_std = qty * std
            val_var = qty * cu_var
            val_abs = qty * cu_abs
            tot_uds += qty
            tot_val_std += val_std
            tot_val_var += val_var
            tot_val_abs += val_abs
            lines_data.append({
                'product_id':       pid,
                'categ_id':         prod.categ_id.id or False,
                'qty_stock':        round(qty, 3),
                'coste_std_actual': round(std, 4),
                'coste_unit_var':   round(cu_var, 4),
                'coste_unit_fijo':  round(cu_fij, 4),
                'coste_unit_abs':   round(cu_abs, 4),
                'valor_std_actual': round(val_std, 2),
                'valor_variable':   round(val_var, 2),
                'valor_absorcion':  round(val_abs, 2),
                'fijos_en_stock':   round(val_abs - val_var, 2),
                'delta_std_abs':    round(val_std - val_abs, 2),
            })

        kpis = {
            'total_variables_periodo':  round(tot_var, 2),
            'total_fijos_periodo':      round(tot_fij, 2),
            'uds_producidas_periodo':   round(uds_producidas, 3),
            'coste_unit_variable':      round(cu_var, 4),
            'coste_unit_fijo':          round(cu_fij, 4),
            'coste_unit_absorcion':     round(cu_abs, 4),
            'uds_stock_total':          round(tot_uds, 3),
            'num_productos_stock':      len(lines_data),
            'valor_stock_actual':       round(tot_val_std, 2),
            'valor_stock_variable':     round(tot_val_var, 2),
            'valor_stock_absorcion':    round(tot_val_abs, 2),
            'diferencia_abs_var':       round(tot_val_abs - tot_val_var, 2),
            'delta_stock_vs_abs':       round(tot_val_std - tot_val_abs, 2),
            'sin_produccion':           sin_produccion,
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.inventory.valuation.fv.line']
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
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_inventory_valuation_fv_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_inventory_valuation_fv_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Valoración inventario — detalle por producto',
            'res_model': 'lira.inventory.valuation.fv.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Valoración Inventario (Fijos/Variables)',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
