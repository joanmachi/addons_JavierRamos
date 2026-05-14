from odoo import models, fields, api


class LiraMrpWipLine(models.Model):
    _name = 'lira.mrp.wip.line'
    _description = 'Línea fabricación en curso (WIP)'
    _order = 'valoracion desc'

    def action_open_source(self):
        """Abre la Orden de Fabricación."""
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

    user_id        = fields.Many2one('res.users', ondelete='cascade', index=True)
    production_id  = fields.Many2one('mrp.production', string='Orden', index=True)
    product_id     = fields.Many2one('product.product', string='Producto', index=True)
    barcode        = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code   = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id       = fields.Many2one('product.category', string='Categoría', index=True)
    referencia     = fields.Char('Referencia')
    estado         = fields.Selection([
        ('confirmed', 'Confirmada'), ('progress', 'En producción'), ('to_close', 'Lista para cerrar'),
    ], string='Estado', index=True)
    qty_prevista   = fields.Float('Cant. prevista', digits=(16, 3))
    coste_mp       = fields.Float('Coste MP (€)', digits=(16, 2))
    coste_horas    = fields.Float('Coste M.O. (€)', digits=(16, 2))
    valoracion     = fields.Float('Valoración WIP (€)', digits=(16, 2))
    fecha_prevista = fields.Date('Entrega prevista')


class LiraMrpWip(models.TransientModel):
    _name = 'lira.mrp.wip'
    _description = 'Fabricación en curso (WIP)'
    _rec_name = 'display_title'

    display_title     = fields.Char(default='Fabricación en Curso (WIP)', readonly=True)
    total_valoracion  = fields.Float('Valoración total WIP (€)', readonly=True)
    coste_mp_total    = fields.Float('Total coste MP (€)', readonly=True)
    coste_horas_total = fields.Float('Total coste M.O. (€)', readonly=True)
    total_confirmadas = fields.Integer('Confirmadas', readonly=True)
    total_en_progreso = fields.Integer('En producción', readonly=True)
    total_para_cerrar = fields.Integer('Listas para cerrar', readonly=True)

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
            if state == 'confirmed': cnt_confirmed += 1
            elif state == 'progress': cnt_progress += 1
            else: cnt_to_close += 1
            coste_mp = coste_horas_prod = 0.0
            if state in ('progress', 'to_close'):
                for move in prod.move_raw_ids:
                    if move.state == 'cancel':
                        continue
                    qty = move.quantity if move.quantity else (move.product_qty or 0.0)
                    price_unit = abs(move.price_unit) if move.price_unit else 0.0
                    if not price_unit:
                        price_unit = move.product_id.standard_price or 0.0
                    coste_mp += qty * price_unit
                for wo in prod.workorder_ids:
                    dur_min = wo.duration if wo.duration else (wo.duration_expected or 0.0)
                    hour_cost = (wo.workcenter_id.costs_hour or 0.0) if wo.workcenter_id else 0.0
                    coste_horas_prod += (dur_min / 60.0) * hour_cost
            valoracion = coste_mp + coste_horas_prod
            total_val += valoracion; total_mp += coste_mp; total_horas += coste_horas_prod
            fecha = prod.date_deadline.date() if prod.date_deadline and hasattr(prod.date_deadline, 'date') else prod.date_deadline
            lines_data.append({
                'production_id': prod.id,
                'product_id':    prod.product_id.id if prod.product_id else False,
                'categ_id':      prod.product_id.categ_id.id if prod.product_id else False,
                'referencia':    prod.name,
                'estado':        state,
                'qty_prevista':  prod.product_qty,
                'coste_mp':      round(coste_mp, 2),
                'coste_horas':   round(coste_horas_prod, 2),
                'valoracion':    round(valoracion, 2),
                'fecha_prevista': fecha,
            })
        kpis = {
            'total_valoracion':  round(total_val, 2),
            'coste_mp_total':    round(total_mp, 2),
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
            Line = self.env['lira.mrp.wip.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_mrp_wip_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_mrp_wip_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Fabricación en curso (WIP) — detalle',
            'res_model': 'lira.mrp.wip.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Fabricación en Curso (WIP)',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
