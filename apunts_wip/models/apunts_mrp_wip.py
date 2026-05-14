from odoo import models, fields, api


class ApuntsMrpWipLine(models.Model):
    _name = 'apunts.mrp.wip.line'
    _description = 'Línea fabricación en curso (WIP)'
    _order = 'valoracion desc'

    user_id = fields.Many2one('res.users', ondelete='cascade', index=True)
    production_id = fields.Many2one('mrp.production', string='Orden', index=True)
    product_id = fields.Many2one('product.product', string='Producto', index=True)
    barcode = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id = fields.Many2one('product.category', string='Categoría', index=True)
    referencia = fields.Char('Referencia')
    estado = fields.Selection([
        ('confirmed', 'Confirmada'),
        ('progress', 'En producción'),
        ('to_close', 'Lista para cerrar'),
    ], string='Estado', index=True)
    qty_prevista = fields.Float('Cant. prevista', digits=(16, 3))
    coste_mp = fields.Float('Coste MP (€)', digits=(16, 2))
    coste_horas = fields.Float('Coste M.O. (€)', digits=(16, 2))
    valoracion = fields.Float('Valoración WIP (€)', digits=(16, 2))
    fecha_prevista = fields.Date('Entrega prevista')

    def action_open_source(self):
        self.ensure_one()
        if not self.production_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Orden de fabricación',
            'res_model': 'mrp.production',
            'res_id': self.production_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ApuntsMrpWip(models.TransientModel):
    _name = 'apunts.mrp.wip'
    _description = 'Fabricación en curso (WIP)'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Fabricación en Curso (WIP)', readonly=True)
    total_valoracion = fields.Float('Valoración total WIP (€)', readonly=True)
    coste_mp_total = fields.Float('Total coste MP (€)', readonly=True)
    coste_horas_total = fields.Float('Total coste M.O. (€)', readonly=True)
    total_confirmadas = fields.Integer('Confirmadas', readonly=True)
    total_en_progreso = fields.Integer('En producción', readonly=True)
    total_para_cerrar = fields.Integer('Listas para cerrar', readonly=True)

    def _apunts_get_pos_for_production(self, production):
        """POs vinculadas a esta OF (por procurement_group u origin)."""
        PO = self.env['purchase.order']
        pos = PO
        if production and production.procurement_group_id:
            pos |= PO.search([
                ('group_id', '=', production.procurement_group_id.id),
                ('state', 'in', ('purchase', 'done')),
            ])
        if production and production.name:
            pos |= PO.search([
                ('origin', 'ilike', production.name),
                ('state', 'in', ('purchase', 'done')),
            ])
        return pos

    def _apunts_get_product_cost(self, product, production=None):
        """Cascada con PRIORIDAD a la PO vinculada a la OF concreta.

        Orden:
        0a. Línea PO con campo custom `fabricacion = production` (vínculo
            manual del cliente, el más exacto).
        0b. PO via procurement_group/origin con ese producto recibido.
        1.  standard_price del producto.
        2.  Promedio ponderado de TODAS las POs recibidas (genérico).
        3.  Última PO confirmada (purchase/done) sin recibir.
        4.  Template / sellers.
        """
        if not product:
            return 0.0

        # 0a. PO line con `fabricacion=production` (vínculo manual exacto del cliente).
        # Usamos `price_subtotal / product_qty` para tener el precio efectivo por
        # unidad PRIMARIA — esto cubre correctamente el caso de UoM secundaria
        # (donde price_unit puede estar en sec, ej. €/kg, mientras que product_qty
        # está en primaria, ej. m).
        if production:
            POL = self.env['purchase.order.line']
            if 'fabricacion' in POL._fields:
                pols = POL.search([
                    ('fabricacion', '=', production.id),
                    ('product_id', '=', product.id),
                    ('order_id.state', 'in', ('purchase', 'done')),
                ])
                if pols:
                    total_qty = sum(pols.mapped('product_qty'))
                    total_amt = sum(pols.mapped('price_subtotal'))
                    if total_qty > 0 and total_amt > 0:
                        return total_amt / total_qty

        # 0b. PO via procurement_group/origin (vínculo automático Odoo)
        if production:
            related = self._apunts_get_pos_for_production(production)
            matched = related.order_line.filtered(
                lambda l: l.product_id.id == product.id and (l.qty_received or 0) > 0
            )
            if matched:
                total_qty = sum(matched.mapped('qty_received'))
                if total_qty > 0:
                    total_amt = sum(l.qty_received * l.price_unit for l in matched)
                    if total_amt > 0:
                        return total_amt / total_qty

        if product.standard_price:
            return product.standard_price
        cr = self.env.cr
        cr.execute("""
            SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE pol.product_id = %s AND po.state IN ('purchase','done') AND pol.qty_received > 0
        """, [product.id])
        row = cr.fetchone()
        avg = float(row[0]) if row and row[0] else 0.0
        if avg > 0:
            return avg
        cr.execute("""
            SELECT pol.price_unit FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE pol.product_id = %s AND po.state IN ('purchase','done') AND pol.price_unit > 0
            ORDER BY po.date_order DESC NULLS LAST, po.id DESC LIMIT 1
        """, [product.id])
        row = cr.fetchone()
        last = float(row[0]) if row and row[0] else 0.0
        if last > 0:
            return last
        tmpl_id = product.product_tmpl_id.id if product.product_tmpl_id else 0
        if tmpl_id:
            cr.execute("""
                SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                JOIN product_product pp ON pp.id = pol.product_id
                WHERE pp.product_tmpl_id = %s AND po.state IN ('purchase','done') AND pol.qty_received > 0
            """, [tmpl_id])
            row = cr.fetchone()
            v = float(row[0]) if row and row[0] else 0.0
            if v > 0:
                return v
        sellers = product.seller_ids.sorted(key=lambda s: (s.sequence or 99, -(s.id or 0)))
        for s in sellers:
            if s.price and s.price > 0:
                return s.price
        return 0.0

    def _build_data(self):
        cid = self.env.company.id
        productions = self.env['mrp.production'].search([
            ('state', 'in', ['confirmed', 'progress', 'to_close']),
            ('company_id', '=', cid),
        ])
        lines_data = []
        total_val = total_mp = total_horas = 0.0
        cnt_confirmed = cnt_progress = cnt_to_close = 0
        for prod in productions:
            state = prod.state
            if state == 'confirmed':
                cnt_confirmed += 1
            elif state == 'progress':
                cnt_progress += 1
            else:
                cnt_to_close += 1
            coste_mp = coste_horas_prod = 0.0
            # Calcular SIEMPRE (incluido state=confirmed) usando qty planificada
            # como fallback. Antes solo entraba si progress/to_close → muchas
            # OF salían a 0.
            for move in prod.move_raw_ids:
                if move.state == 'cancel':
                    continue
                qty = move.quantity if move.quantity else (move.product_qty or 0.0)
                price_unit = abs(move.price_unit) if move.price_unit else 0.0
                if not price_unit:
                    price_unit = self._apunts_get_product_cost(move.product_id, production=prod)
                coste_mp += qty * price_unit
            for wo in prod.workorder_ids:
                dur_min = wo.duration if wo.duration else (wo.duration_expected or 0.0)
                hour_cost = (wo.workcenter_id.costs_hour or 0.0) if wo.workcenter_id else 0.0
                coste_horas_prod += (dur_min / 60.0) * hour_cost
            valoracion = coste_mp + coste_horas_prod
            total_val += valoracion
            total_mp += coste_mp
            total_horas += coste_horas_prod
            fecha = prod.date_deadline.date() if prod.date_deadline and hasattr(prod.date_deadline, 'date') else prod.date_deadline
            lines_data.append({
                'production_id': prod.id,
                'product_id': prod.product_id.id if prod.product_id else False,
                'categ_id': prod.product_id.categ_id.id if prod.product_id else False,
                'referencia': prod.name,
                'estado': state,
                'qty_prevista': prod.product_qty,
                'coste_mp': round(coste_mp, 2),
                'coste_horas': round(coste_horas_prod, 2),
                'valoracion': round(valoracion, 2),
                'fecha_prevista': fecha,
            })
        kpis = {
            'total_valoracion': round(total_val, 2),
            'coste_mp_total': round(total_mp, 2),
            'coste_horas_total': round(total_horas, 2),
            'total_confirmadas': cnt_confirmed,
            'total_en_progreso': cnt_progress,
            'total_para_cerrar': cnt_to_close,
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['apunts.mrp.wip.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('apunts_wip.view_apunts_mrp_wip_line_list', raise_if_not_found=False)
        sv = self.env.ref('apunts_wip.view_apunts_mrp_wip_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Fabricación en curso (WIP) — detalle',
            'res_model': 'apunts.mrp.wip.line',
            'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
        }
        if lv:
            action['views'] = [(lv.id, 'list')]
        if sv:
            action['search_view_id'] = [sv.id, 'search']
        return action

    def action_refresh(self):
        self._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def action_open(self):
        rec = self.create({})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Fabricación en Curso (WIP)',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
