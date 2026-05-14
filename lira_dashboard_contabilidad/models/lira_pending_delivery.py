from odoo import api, fields, models
from datetime import date
from collections import defaultdict


class LiraPendingDeliveryLine(models.Model):
    _name = 'lira.pending.delivery.line'
    _description = 'Línea de pedido pendiente de entrega'
    _order = 'valor_pendiente desc'

    def action_open_source(self):
        """Abre el pedido de venta original."""
        self.ensure_one()
        so = self.env['sale.order'].search([('name','=',self.pedido)], limit=1)
        if not so:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedido de venta',
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }

    user_id          = fields.Many2one('res.users', ondelete='cascade', index=True)
    pedido           = fields.Char(string='Pedido')
    fecha_pedido     = fields.Date(string='Fecha pedido')
    partner_id       = fields.Many2one('res.partner', string='Cliente', index=True)
    partner_vat      = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city     = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    partner_ref      = fields.Char(related='partner_id.ref', string='Ref. cliente', store=False)
    product_id       = fields.Many2one('product.product', string='Producto', index=True)
    barcode          = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code     = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id         = fields.Many2one('product.category', string='Categoría', index=True)
    qty_pedida       = fields.Float(string='Uds. pedidas', digits=(16, 2))
    qty_entregada    = fields.Float(string='Uds. entregadas', digits=(16, 2))
    qty_pendiente    = fields.Float(string='Uds. pendientes', digits=(16, 2))
    pct_entregado    = fields.Float(string='% entregado', digits=(16, 1))
    stock_disponible = fields.Float(string='Stock disp.', digits=(16, 2))
    precio_unit      = fields.Float(string='Precio unit. (€)', digits=(16, 2))
    valor_pendiente  = fields.Float(string='Valor pendiente (€)', digits=(16, 2))
    dias_espera      = fields.Integer(string='Días en espera')


class LiraPendingDelivery(models.TransientModel):
    _name = 'lira.pending.delivery'
    _description = 'Pedidos pendientes de entrega'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Pedidos Pendientes de Entrega', readonly=True)
    total_valor   = fields.Float(string='Valor pendiente total (€)', readonly=True)
    num_pedidos   = fields.Integer(string='Pedidos con pendiente', readonly=True)
    num_clientes  = fields.Integer(string='Clientes esperando', readonly=True)
    top_cliente   = fields.Char(string='Top cliente', readonly=True)
    top_producto  = fields.Char(string='Top producto', readonly=True)

    def _build_data(self):
        cid = self.env.company.id
        hoy = date.today()
        lines = self.env['sale.order.line'].search([
            ('company_id', '=', cid),
            ('order_id.state', 'in', ['sale', 'done']),
            ('product_id.type', 'in', ['product', 'consu']),
        ])
        vals = []
        for l in lines:
            pendiente = l.product_uom_qty - l.qty_delivered
            if pendiente <= 0.001:
                continue
            fecha = l.order_id.date_order.date() if l.order_id.date_order else hoy
            dias = (hoy - fecha).days
            pct = round(l.qty_delivered / l.product_uom_qty * 100, 1) if l.product_uom_qty else 0.0
            vals.append({
                'pedido':           l.order_id.name,
                'fecha_pedido':     fecha,
                'partner_id':       l.order_id.partner_id.id,
                'product_id':       l.product_id.id,
                'categ_id':         l.product_id.categ_id.id or False,
                'qty_pedida':       round(l.product_uom_qty, 2),
                'qty_entregada':    round(l.qty_delivered, 2),
                'qty_pendiente':    round(pendiente, 2),
                'pct_entregado':    pct,
                'stock_disponible': round(l.product_id.virtual_available, 2),
                'precio_unit':      round(l.price_unit, 2),
                'valor_pendiente':  round(pendiente * l.price_unit, 2),
                'dias_espera':      dias,
            })
        by_cliente  = defaultdict(float)
        by_producto = defaultdict(float)
        for v in vals:
            by_cliente[v['partner_id']]  += v['valor_pendiente']
            by_producto[v['product_id']] += v['valor_pendiente']
        top_c_id = max(by_cliente,  key=by_cliente.get)  if by_cliente  else False
        top_p_id = max(by_producto, key=by_producto.get) if by_producto else False
        kpis = {
            'total_valor':  round(sum(v['valor_pendiente'] for v in vals), 2),
            'num_pedidos':  len({v['pedido'] for v in vals}),
            'num_clientes': len({v['partner_id'] for v in vals}),
            'top_cliente':  self.env['res.partner'].browse(top_c_id).name if top_c_id else '—',
            'top_producto': self.env['product.product'].browse(top_p_id).display_name if top_p_id else '—',
        }
        return vals, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            vals, kpis = rec._build_data()
            Line = self.env['lira.pending.delivery.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for v in vals:
                Line.create({**v, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_pending_delivery_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_pending_delivery_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Pedidos pendientes de entrega — detalle',
            'res_model': 'lira.pending.delivery.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Pedidos Pendientes de Entrega',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
