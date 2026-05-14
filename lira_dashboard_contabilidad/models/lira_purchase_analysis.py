from odoo import models, fields, api
from datetime import date
from collections import defaultdict


class LiraPurchaseLine(models.Model):
    _name = 'lira.purchase.line'
    _description = 'Línea análisis de compras'
    _order = 'importe desc'

    def action_open_source(self):
        """Abre pedidos de compra filtrados según la dimensión de agrupación."""
        self.ensure_one()
        domain = [('state', 'in', ['purchase','done'])]
        name = 'Pedidos de compra'
        if self.agrupar_por == 'supplier' and self.partner_id:
            domain.append(('partner_id.commercial_partner_id','=',self.partner_id.id))
            name = f'Pedidos — {self.partner_id.name}'
        elif self.agrupar_por == 'product' and self.product_id:
            domain.append(('order_line.product_id','=',self.product_id.id))
            name = f'Pedidos con producto — {self.product_id.display_name}'
        elif self.agrupar_por == 'category' and self.categ_id:
            domain.append(('order_line.product_id.categ_id','=',self.categ_id.id))
            name = f'Pedidos categoría — {self.categ_id.name}'
        return {
            'type': 'ir.actions.act_window', 'name': name,
            'res_model': 'purchase.order', 'view_mode': 'list,form',
            'domain': domain, 'target': 'current',
        }

    user_id      = fields.Many2one('res.users', ondelete='cascade', index=True)
    rank         = fields.Integer('Pos.')
    label        = fields.Char('Nombre')
    # Many2one opcionales: se rellenan según la agrupación activa
    partner_id   = fields.Many2one('res.partner', string='Proveedor', index=True)
    product_id   = fields.Many2one('product.product', string='Producto', index=True)
    categ_id     = fields.Many2one('product.category', string='Categoría', index=True)
    qty          = fields.Float('Uds.', digits=(16, 2))
    importe      = fields.Float('Compras (€)', digits=(16, 2))
    num_pedidos  = fields.Integer('Pedidos')
    ticket_medio = fields.Float('Ticket medio (€)', digits=(16, 2))
    ultima_fecha = fields.Date('Último pedido')
    pct_compras  = fields.Float('% s/total', digits=(16, 1))
    agrupar_por  = fields.Char('Agrupación')


class LiraPurchaseAnalysis(models.TransientModel):
    _name = 'lira.purchase.analysis'
    _description = 'Análisis de compras'
    _rec_name = 'display_title'

    display_title   = fields.Char(default='Análisis de Compras', readonly=True)
    date_from       = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to         = fields.Date('Hasta', default=fields.Date.today)
    agrupar_por     = fields.Selection([
        ('supplier', 'Por proveedor'), ('product', 'Por producto'),
        ('category', 'Por categoría'), ('month', 'Por mes'),
    ], default='supplier', required=True, string='Agrupar por')
    total_compras   = fields.Float('Total compras (€)', readonly=True)
    num_proveedores = fields.Integer('Proveedores activos', readonly=True)
    num_productos   = fields.Integer('Productos comprados', readonly=True)
    top_proveedor   = fields.Char('Top proveedor', readonly=True)
    top_producto    = fields.Char('Top producto', readonly=True)

    def _build_data(self):
        rec = self
        df = rec.date_from or date.today().replace(month=1, day=1)
        dt = rec.date_to   or date.today()
        lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ['purchase', 'done']),
            ('order_id.date_order', '>=', str(df)),
            ('order_id.date_order', '<=', str(dt) + ' 23:59:59'),
            ('order_id.company_id', '=', self.env.company.id),
        ])
        groups = defaultdict(lambda: {'label': '', 'importe': 0.0, 'qty': 0.0,
                                       'pedidos': set(), 'fechas': [],
                                       'partner': None, 'product': None, 'categ': None})
        for l in lines:
            order = l.order_id
            if rec.agrupar_por == 'supplier':
                cp = order.partner_id.commercial_partner_id
                key = cp.id
                groups[key]['label'] = cp.name or '—'
                groups[key]['partner'] = cp.id
            elif rec.agrupar_por == 'product':
                if not l.product_id: continue
                key = l.product_id.id
                groups[key]['label'] = l.product_id.display_name or '—'
                groups[key]['product'] = l.product_id.id
            elif rec.agrupar_por == 'category':
                cat = l.product_id.categ_id if l.product_id else False
                key = cat.id if cat else 0
                groups[key]['label'] = cat.name if cat else 'Sin categoría'
                groups[key]['categ'] = cat.id if cat else False
            elif rec.agrupar_por == 'month':
                if order.date_order:
                    key = order.date_order.strftime('%Y-%m')
                    groups[key]['label'] = order.date_order.strftime('%b %Y')
                else:
                    continue
            groups[key]['importe'] += l.price_subtotal
            groups[key]['qty'] += l.product_qty
            groups[key]['pedidos'].add(order.id)
            if order.date_order:
                groups[key]['fechas'].append(order.date_order.date())
        total_c = sum(g['importe'] for g in groups.values())
        result = []
        for key, g in sorted(groups.items(), key=lambda x: -x[1]['importe']):
            if g['importe'] <= 0: continue
            n_ped = len(g['pedidos'])
            result.append({
                'label': g['label'], 'qty': g['qty'], 'importe': g['importe'],
                'num_pedidos': n_ped,
                'ticket_medio': round(g['importe'] / n_ped, 2) if n_ped else 0.0,
                'ultima_fecha': max(g['fechas']) if g['fechas'] else False,
                'pct_compras': round(g['importe'] / total_c * 100, 1) if total_c else 0.0,
                'partner_id': g['partner'], 'product_id': g['product'], 'categ_id': g['categ'],
                'agrupar_por': rec.agrupar_por,
            })
        top_prov = max(
            (g for g in [{'label': l.order_id.partner_id.commercial_partner_id.name, 'v': l.price_subtotal} for l in lines]),
            key=lambda x: x['v'], default={'label': '—'}
        )['label'] if lines else '—'
        top_prod = max(
            (g for g in [{'label': l.product_id.display_name or '—', 'v': l.price_subtotal} for l in lines if l.product_id]),
            key=lambda x: x['v'], default={'label': '—'}
        )['label'] if lines else '—'
        kpis = {
            'total_compras': total_c,
            'num_proveedores': len(set(l.order_id.partner_id.commercial_partner_id.id for l in lines)),
            'num_productos': len(set(l.product_id.id for l in lines if l.product_id)),
            'top_proveedor': top_prov, 'top_producto': top_prod,
        }
        return result, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            result, kpis = rec._build_data()
            Line = self.env['lira.purchase.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for i, d in enumerate(result, 1):
                Line.create({**d, 'rank': i, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_purchase_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_purchase_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Análisis de compras — ranking',
            'res_model': 'lira.purchase.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    @api.onchange('date_from', 'date_to', 'agrupar_por')
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
        return {'type': 'ir.actions.act_window', 'name': 'Análisis de Compras',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
