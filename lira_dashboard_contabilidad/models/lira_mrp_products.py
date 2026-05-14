from odoo import models, fields, api
from collections import defaultdict
from datetime import date as _date


# ── PRODUCTOS FABRICÁNDOSE (en producción, no terminados) ─────────────────────

class LiraMrpInProgressLine(models.Model):
    _name = 'lira.mrp.in.progress.line'
    _description = 'Línea productos fabricándose no terminados'
    _order = 'qty_restante desc'

    def action_open_source(self):
        """Abre todas las OFs en producción de este producto."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'OFs en producción — {self.product_id.display_name}',
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'domain': [
                ('state', '=', 'progress'),
                ('product_id', '=', self.product_id.id),
            ],
            'target': 'current',
        }

    user_id         = fields.Many2one('res.users', ondelete='cascade', index=True)
    product_id      = fields.Many2one('product.product', string='Producto', index=True)
    barcode         = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code    = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id        = fields.Many2one('product.category', string='Categoría', index=True)
    num_ordenes     = fields.Integer('Órdenes')
    qty_a_producir  = fields.Float('Cant. a producir', digits=(16, 3))
    qty_producida   = fields.Float('Cant. producida', digits=(16, 3))
    qty_restante    = fields.Float('Cant. restante', digits=(16, 3))
    pct_completado  = fields.Float('% completado', digits=(16, 1))
    proxima_entrega = fields.Date('Más próxima')


class LiraMrpInProgress(models.TransientModel):
    _name = 'lira.mrp.in.progress'
    _description = 'Productos fabricándose no terminados'
    _rec_name = 'display_title'

    display_title      = fields.Char(default='Productos Fabricándose (No Terminados)', readonly=True)
    total_ordenes      = fields.Integer('Órdenes en producción', readonly=True)
    total_productos    = fields.Integer('Productos distintos', readonly=True)
    qty_total_restante = fields.Float('Unidades totales restantes', readonly=True, digits=(16, 3))

    def _build_data(self):
        cid = self.env.company.id
        productions = self.env['mrp.production'].search([
            ('state', '=', 'progress'),
            ('company_id', '=', cid),
        ])
        groups = defaultdict(lambda: {
            'product': None, 'categ': False, 'ordenes': 0,
            'qty_plan': 0.0, 'qty_prod': 0.0, 'fechas': [],
        })
        for prod in productions:
            pid = prod.product_id.id
            groups[pid]['product'] = prod.product_id
            groups[pid]['categ'] = prod.product_id.categ_id.id if prod.product_id else False
            groups[pid]['ordenes'] += 1
            groups[pid]['qty_plan'] += prod.product_qty
            groups[pid]['qty_prod'] += prod.qty_producing or 0.0
            if prod.date_deadline:
                groups[pid]['fechas'].append(prod.date_deadline)
        lines_data = []
        for pid, g in groups.items():
            if not g['product']:
                continue
            restante = g['qty_plan'] - g['qty_prod']
            pct = round(g['qty_prod'] / g['qty_plan'] * 100, 1) if g['qty_plan'] else 0.0
            fechas = g['fechas']
            proxima = min(f.date() if hasattr(f, 'date') else f for f in fechas) if fechas else None
            lines_data.append({
                'product_id': pid,
                'categ_id': g['categ'],
                'num_ordenes': g['ordenes'],
                'qty_a_producir': round(g['qty_plan'], 3),
                'qty_producida': round(g['qty_prod'], 3),
                'qty_restante': round(restante, 3),
                'pct_completado': pct,
                'proxima_entrega': proxima,
            })
        lines_data.sort(key=lambda x: -x['qty_restante'])
        kpis = {
            'total_ordenes': sum(d['num_ordenes'] for d in lines_data),
            'total_productos': len(lines_data),
            'qty_total_restante': round(sum(d['qty_restante'] for d in lines_data), 3),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.mrp.in.progress.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_mrp_in_progress_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_mrp_in_progress_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Fabricándose — detalle',
            'res_model': 'lira.mrp.in.progress.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Productos Fabricándose (No Terminados)',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}


# ── PRODUCTOS PENDIENTES DE FABRICAR (confirmados, no iniciados) ──────────────

class LiraMrpToProduceLine(models.Model):
    _name = 'lira.mrp.to.produce.line'
    _description = 'Línea productos pendientes de fabricar'
    _order = 'proxima_fecha asc, qty_total desc'

    def action_open_source(self):
        """Abre todas las OFs confirmadas de este producto."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'OFs confirmadas — {self.product_id.display_name}',
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'domain': [
                ('state', '=', 'confirmed'),
                ('product_id', '=', self.product_id.id),
            ],
            'target': 'current',
        }

    user_id       = fields.Many2one('res.users', ondelete='cascade', index=True)
    product_id    = fields.Many2one('product.product', string='Producto', index=True)
    barcode       = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code  = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id      = fields.Many2one('product.category', string='Categoría', index=True)
    num_ordenes   = fields.Integer('Órdenes')
    qty_total     = fields.Float('Cant. a fabricar', digits=(16, 3))
    stock_actual  = fields.Float('Stock actual', digits=(16, 3))
    proxima_fecha = fields.Date('Fecha más próxima')


class LiraMrpToProduce(models.TransientModel):
    _name = 'lira.mrp.to.produce'
    _description = 'Productos pendientes de fabricar'
    _rec_name = 'display_title'

    display_title   = fields.Char(default='Productos Pendientes de Fabricar', readonly=True)
    total_ordenes   = fields.Integer('Órdenes confirmadas', readonly=True)
    total_productos = fields.Integer('Productos distintos', readonly=True)
    qty_total       = fields.Float('Total unidades a fabricar', readonly=True, digits=(16, 3))

    def _build_data(self):
        cid = self.env.company.id
        productions = self.env['mrp.production'].search([
            ('state', '=', 'confirmed'),
            ('company_id', '=', cid),
        ])
        groups = defaultdict(lambda: {
            'product': None, 'categ': False, 'ordenes': 0,
            'qty_total': 0.0, 'fechas': [],
        })
        for prod in productions:
            pid = prod.product_id.id
            groups[pid]['product'] = prod.product_id
            groups[pid]['categ'] = prod.product_id.categ_id.id if prod.product_id else False
            groups[pid]['ordenes'] += 1
            groups[pid]['qty_total'] += prod.product_qty
            if prod.date_deadline:
                groups[pid]['fechas'].append(prod.date_deadline)
        lines_data = []
        for pid, g in groups.items():
            if not g['product']:
                continue
            fechas = g['fechas']
            proxima = min(f.date() if hasattr(f, 'date') else f for f in fechas) if fechas else None
            lines_data.append({
                'product_id': pid,
                'categ_id': g['categ'],
                'num_ordenes': g['ordenes'],
                'qty_total': round(g['qty_total'], 3),
                'stock_actual': round(g['product'].qty_available, 3),
                'proxima_fecha': proxima,
            })
        _max = _date(9999, 12, 31)
        lines_data.sort(key=lambda x: (x['proxima_fecha'] or _max, -x['qty_total']))
        kpis = {
            'total_ordenes': sum(d['num_ordenes'] for d in lines_data),
            'total_productos': len(lines_data),
            'qty_total': round(sum(d['qty_total'] for d in lines_data), 3),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.mrp.to.produce.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_mrp_to_produce_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_mrp_to_produce_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Pendientes de fabricar — detalle',
            'res_model': 'lira.mrp.to.produce.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Productos Pendientes de Fabricar',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
