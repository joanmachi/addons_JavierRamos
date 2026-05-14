from odoo import models, fields, api


class LiraWipValuationLine(models.Model):
    _name = 'lira.wip.valuation.line'
    _description = 'Línea valoración de producto en curso'
    _order = 'valor desc'

    def action_open_source(self):
        """Abre la OF asociada si existe, si no el pedido de venta."""
        self.ensure_one()
        if self.production_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Orden de fabricación',
                'res_model': 'mrp.production',
                'res_id': self.production_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Pedido de venta',
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False

    user_id       = fields.Many2one('res.users', ondelete='cascade', index=True)
    sale_order_id = fields.Many2one('sale.order', string='Pedido', index=True)
    sol_id        = fields.Many2one('sale.order.line', string='Línea pedido')
    partner_id    = fields.Many2one('res.partner', string='Cliente', index=True)
    partner_vat   = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city  = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    product_id    = fields.Many2one('product.product', string='Producto', index=True)
    barcode       = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code  = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id      = fields.Many2one('product.category', string='Categoría', index=True)
    production_id = fields.Many2one('mrp.production', string='OF')

    # ─── Estados reales (para filtrar/agrupar) ────────────────────────────
    production_state = fields.Selection([
        ('no_of',     'Sin OF'),
        ('draft',     'Borrador'),
        ('confirmed', 'Confirmada'),
        ('progress',  'En curso'),
        ('to_close',  'Pdte. cerrar'),
        ('done',      'Terminada'),
        ('cancel',    'Cancelada'),
    ], string='Estado OF', index=True)

    mp_state = fields.Selection([
        ('no_aplica',  'No aplica (sin OF)'),
        ('sin_mp',     'Sin MP ni PO'),
        ('mp_pedida',  'MP pedida (PO confirmada)'),
        ('mp_parcial', 'MP parcialmente reservada'),
        ('mp_reservada', 'MP reservada'),
        ('mp_consumida', 'MP consumida'),
    ], string='Estado MP', index=True)

    delivery_state = fields.Selection([
        ('no_entregado', 'Sin entregar'),
        ('parcial',      'Entrega parcial'),
        ('entregado',    'Entregado completo'),
    ], string='Estado entrega', index=True)

    invoice_state = fields.Selection([
        ('no_facturado', 'Sin facturar'),
        ('parcial',      'Factura parcial'),
        ('facturado',    'Facturado completo'),
    ], string='Estado factura', index=True)

    # ─── Cantidades y valores ─────────────────────────────────────────────
    qty_pedida    = fields.Float('Cant. pedida', digits=(16, 3))
    qty_entregada = fields.Float('Cant. entregada', digits=(16, 3))
    qty_facturada = fields.Float('Cant. facturada', digits=(16, 3))
    coste_mp      = fields.Float('Coste MP (€)', digits=(16, 2))
    coste_fab     = fields.Float('Coste M.O. (€)', digits=(16, 2))
    precio_venta  = fields.Float('Precio venta (€)', digits=(16, 2))
    valor         = fields.Float('Valoración (€)', digits=(16, 2))
    fecha_pedido  = fields.Date('Fecha pedido')
    fecha_entrega = fields.Date('Entrega prevista')


class LiraWipValuation(models.TransientModel):
    _name = 'lira.wip.valuation'
    _description = 'Valoración de Producto en Curso'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Valoración de Producto en Curso', readonly=True)

    valor_total     = fields.Float('Valoración total (€)', readonly=True)
    coste_total_mp  = fields.Float('Coste MP acumulado (€)', readonly=True)
    coste_total_fab = fields.Float('Coste M.O. acumulado (€)', readonly=True)
    precio_total    = fields.Float('Precio venta fabricados/entregados (€)', readonly=True)
    num_lineas      = fields.Integer('Líneas totales', readonly=True)
    num_sin_valor   = fields.Integer('Líneas con valor 0', readonly=True)
    num_con_of      = fields.Integer('Líneas con OF', readonly=True)

    # ────────────────────────────────────────────────────────────────────────
    # Resolución OF ↔ línea de pedido
    # ────────────────────────────────────────────────────────────────────────
    def _find_mo_for_sol(self, sol):
        """Busca la orden de fabricación asociada a una línea de pedido."""
        Production = self.env['mrp.production']
        if 'sale_line_id' in Production._fields:
            prod = Production.search([
                ('sale_line_id', '=', sol.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if prod:
                return prod
        prod = Production.search([
            ('origin', 'ilike', sol.order_id.name),
            ('product_id', '=', sol.product_id.id),
            ('state', '!=', 'cancel'),
        ], limit=1)
        return prod

    def _mp_on_purchase_order(self, prod):
        """¿Algún componente está pedido en un PO confirmado sin recibir?"""
        if not prod or not prod.move_raw_ids:
            return False
        component_ids = prod.move_raw_ids.filtered(lambda m: m.state != 'cancel').mapped('product_id.id')
        if not component_ids:
            return False
        POL = self.env['purchase.order.line']
        pols = POL.search([
            ('product_id', 'in', component_ids),
            ('order_id.state', 'in', ['purchase', 'done']),
            ('order_id.company_id', '=', self.env.company.id),
        ])
        for l in pols:
            if (l.product_qty or 0) - (l.qty_received or 0) > 0.001:
                return True
        return False

    def _mp_state_for_production(self, prod):
        """Determina el estado de MP según reservation_state y estado OF."""
        if not prod:
            return 'no_aplica'
        if prod.state in ('progress', 'to_close', 'done'):
            return 'mp_consumida'
        # estado confirmed / draft
        rs = prod.reservation_state  # confirmed, waiting, assigned, partially_available
        if rs == 'assigned':
            return 'mp_reservada'
        if rs == 'partially_available':
            return 'mp_parcial'
        # No reservado: ¿hay PO?
        if self._mp_on_purchase_order(prod):
            return 'mp_pedida'
        return 'sin_mp'

    # ────────────────────────────────────────────────────────────────────────
    # Cálculo de valor según las 7 reglas del contable
    # ────────────────────────────────────────────────────────────────────────
    def _calc_value(self, sol, prod, production_state, mp_state, delivery_state, invoice_state):
        precio_venta = sol.price_subtotal or 0.0
        coste_mp = 0.0
        coste_fab = 0.0

        # Regla 7: Facturado (total o parcial) → precio venta
        if invoice_state in ('facturado', 'parcial') and (sol.qty_invoiced or 0) > 0:
            return precio_venta, coste_mp, coste_fab
        # Regla 6: Entregado completo, no facturado → precio venta
        if delivery_state == 'entregado':
            return precio_venta, coste_mp, coste_fab
        # Regla 5: OF terminada → precio venta
        if production_state == 'done':
            return precio_venta, coste_mp, coste_fab

        # Si hay OF en progreso o terminada sin entregar
        if prod:
            if production_state in ('progress', 'to_close'):
                # Regla 4: MP consumida + M.O. hasta la fecha
                # Con fallbacks: si quantity consumida = 0, usar product_qty planificada.
                # Para el precio: price_unit del move (valoración real) o standard_price del producto.
                coste_mp = 0.0
                for m in prod.move_raw_ids:
                    if m.state == 'cancel':
                        continue
                    qty = m.quantity if m.quantity else (m.product_qty or 0.0)
                    price_unit = abs(m.price_unit) if m.price_unit else 0.0
                    if not price_unit:
                        price_unit = m.product_id.standard_price or 0.0
                    coste_mp += qty * price_unit

                # M.O.: usar duration real, fallback a duration_expected si aún no hay partes
                coste_fab = 0.0
                for wo in prod.workorder_ids:
                    dur_min = wo.duration if wo.duration else (wo.duration_expected or 0.0)
                    hour_cost = (wo.workcenter_id.costs_hour or 0.0) if wo.workcenter_id else 0.0
                    coste_fab += (dur_min / 60.0) * hour_cost
                return coste_mp + coste_fab, coste_mp, coste_fab

            if production_state == 'confirmed':
                # Regla 3: MP reservada → coste MP prevista
                if mp_state in ('mp_reservada', 'mp_parcial'):
                    coste_mp = 0.0
                    for m in prod.move_raw_ids:
                        if m.state == 'cancel':
                            continue
                        qty = m.product_qty or 0.0
                        price_unit = abs(m.price_unit) if m.price_unit else 0.0
                        if not price_unit:
                            price_unit = m.product_id.standard_price or 0.0
                        coste_mp += qty * price_unit
                    return coste_mp, coste_mp, coste_fab
                # Reglas 1 y 2: sin MP o MP pedida sin recibir → valor 0
                return 0.0, 0.0, 0.0

        # Sin OF → valor 0
        return 0.0, 0.0, 0.0

    # ────────────────────────────────────────────────────────────────────────
    def _build_data(self):
        cid = self.env.company.id
        sol_lines = self.env['sale.order.line'].search([
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.company_id', '=', cid),
            ('product_id.type', 'in', ['product', 'consu']),
            ('product_uom_qty', '>', 0),
        ])
        lines_data = []
        total_val = total_mp = total_fab = total_precio_fab = 0.0
        num_sin_valor = num_con_of = 0

        for sol in sol_lines:
            prod = self._find_mo_for_sol(sol)
            qty = sol.product_uom_qty or 0.0
            entregada = sol.qty_delivered or 0.0
            facturada = sol.qty_invoiced or 0.0

            # Estado OF
            if not prod:
                production_state = 'no_of'
            else:
                production_state = prod.state
                num_con_of += 1

            # Estado MP
            mp_state = self._mp_state_for_production(prod)

            # Estado entrega
            if qty > 0 and entregada >= qty - 0.001:
                delivery_state = 'entregado'
            elif entregada > 0.001:
                delivery_state = 'parcial'
            else:
                delivery_state = 'no_entregado'

            # Estado factura
            if qty > 0 and facturada >= qty - 0.001:
                invoice_state = 'facturado'
            elif facturada > 0.001:
                invoice_state = 'parcial'
            else:
                invoice_state = 'no_facturado'

            valor, coste_mp, coste_fab = self._calc_value(
                sol, prod, production_state, mp_state, delivery_state, invoice_state,
            )
            total_val += valor
            total_mp += coste_mp
            total_fab += coste_fab
            if production_state == 'done' or delivery_state in ('entregado', 'parcial') or invoice_state != 'no_facturado':
                total_precio_fab += valor
            if valor <= 0.001:
                num_sin_valor += 1

            fecha_ped = sol.order_id.date_order.date() if sol.order_id.date_order and hasattr(sol.order_id.date_order, 'date') else sol.order_id.date_order

            lines_data.append({
                'sale_order_id': sol.order_id.id,
                'sol_id': sol.id,
                'partner_id': sol.order_id.partner_id.commercial_partner_id.id if sol.order_id.partner_id else False,
                'product_id': sol.product_id.id if sol.product_id else False,
                'categ_id': sol.product_id.categ_id.id if sol.product_id else False,
                'production_id': prod.id if prod else False,
                'production_state': production_state,
                'mp_state': mp_state,
                'delivery_state': delivery_state,
                'invoice_state': invoice_state,
                'qty_pedida': qty,
                'qty_entregada': entregada,
                'qty_facturada': facturada,
                'coste_mp': round(coste_mp, 2),
                'coste_fab': round(coste_fab, 2),
                'precio_venta': round(sol.price_subtotal or 0.0, 2),
                'valor': round(valor, 2),
                'fecha_pedido': fecha_ped,
                'fecha_entrega': sol.order_id.commitment_date.date() if hasattr(sol.order_id, 'commitment_date') and sol.order_id.commitment_date and hasattr(sol.order_id.commitment_date, 'date') else False,
            })

        kpis = {
            'valor_total': round(total_val, 2),
            'coste_total_mp': round(total_mp, 2),
            'coste_total_fab': round(total_fab, 2),
            'precio_total': round(total_precio_fab, 2),
            'num_lineas': len(lines_data),
            'num_sin_valor': num_sin_valor,
            'num_con_of': num_con_of,
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.wip.valuation.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_wip_valuation_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_wip_valuation_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Valoración de producto en curso — detalle',
            'res_model': 'lira.wip.valuation.line', 'view_mode': 'list',
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
        rec = self.create({})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Valoración de Producto en Curso',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
