from odoo import models, fields, api


# ── RECIBIDOS SIN FACTURA ─────────────────────────────────────────────────────

class LiraPurchaseReceivedLine(models.Model):
    _name = 'lira.purchase.received.line'
    _description = 'Línea compras recibidas pendientes de factura'
    _order = 'importe desc'

    def action_open_source(self):
        """Abre el pedido de compra original."""
        self.ensure_one()
        po = self.env['purchase.order'].search([('name','=',self.pedido)], limit=1)
        if not po:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedido de compra',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    user_id         = fields.Many2one('res.users', ondelete='cascade', index=True)
    partner_id      = fields.Many2one('res.partner', string='Proveedor', index=True)
    partner_vat     = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city    = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    pedido          = fields.Char('Pedido')
    product_id      = fields.Many2one('product.product', string='Producto', index=True)
    barcode         = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code    = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id        = fields.Many2one('product.category', string='Categoría', index=True)
    qty_recibida    = fields.Float('Cant. recibida', digits=(16, 3))
    qty_facturada   = fields.Float('Cant. facturada', digits=(16, 3))
    qty_pendiente   = fields.Float('Cant. pendiente', digits=(16, 3))
    precio_unitario = fields.Float('Precio unit. (€)', digits=(16, 4))
    importe         = fields.Float('Importe pendiente (€)', digits=(16, 2))
    fecha_pedido    = fields.Date('Fecha pedido')


class LiraPurchaseReceived(models.TransientModel):
    _name = 'lira.purchase.received'
    _description = 'Compras recibidas pendientes de factura'
    _rec_name = 'display_title'

    display_title   = fields.Char(default='Compras Recibidas — Pendientes de Factura', readonly=True)
    total_pendiente = fields.Float('Total pendiente de facturar (€)', readonly=True)
    num_lineas      = fields.Integer('Líneas pendientes', readonly=True)
    num_proveedores = fields.Integer('Proveedores distintos', readonly=True)

    def _build_data(self):
        cid = self.env.company.id
        po_lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ['purchase', 'done']),
            ('order_id.company_id', '=', cid),
            ('qty_received', '>', 0),
        ])
        lines_data = []
        total = 0.0
        proveedores = set()
        for l in po_lines:
            pendiente = l.qty_received - l.qty_invoiced
            if pendiente <= 0.001:
                continue
            importe = round(pendiente * l.price_unit, 2)
            total += importe
            partner = l.order_id.partner_id.commercial_partner_id
            proveedores.add(partner.id)
            fecha = None
            if l.order_id.date_order:
                fecha = l.order_id.date_order.date() if hasattr(l.order_id.date_order, 'date') else l.order_id.date_order
            lines_data.append({
                'partner_id': partner.id,
                'pedido': l.order_id.name,
                'product_id': l.product_id.id if l.product_id else False,
                'categ_id': l.product_id.categ_id.id if l.product_id else False,
                'qty_recibida': l.qty_received,
                'qty_facturada': l.qty_invoiced,
                'qty_pendiente': round(pendiente, 3),
                'precio_unitario': l.price_unit,
                'importe': importe,
                'fecha_pedido': fecha,
            })
        lines_data.sort(key=lambda x: -x['importe'])
        kpis = {
            'total_pendiente': round(total, 2),
            'num_lineas': len(lines_data),
            'num_proveedores': len(proveedores),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.purchase.received.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_purchase_received_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_purchase_received_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Compras recibidas sin factura — detalle',
            'res_model': 'lira.purchase.received.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Compras Recibidas — Pendientes de Factura',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}


# ── CONFIRMADOS SIN RECIBIR ───────────────────────────────────────────────────

class LiraPurchasePendingLine(models.Model):
    _name = 'lira.purchase.pending.line'
    _description = 'Línea compras confirmadas pendientes de recibir'
    _order = 'importe desc'

    def action_open_source(self):
        """Abre el pedido de compra original."""
        self.ensure_one()
        po = self.env['purchase.order'].search([('name','=',self.pedido)], limit=1)
        if not po:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedido de compra',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    user_id         = fields.Many2one('res.users', ondelete='cascade', index=True)
    partner_id      = fields.Many2one('res.partner', string='Proveedor', index=True)
    partner_vat     = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city    = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    pedido          = fields.Char('Pedido')
    product_id      = fields.Many2one('product.product', string='Producto', index=True)
    barcode         = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    default_code    = fields.Char(related='product_id.default_code', string='Ref. interna', store=False)
    categ_id        = fields.Many2one('product.category', string='Categoría', index=True)
    qty_pedida      = fields.Float('Cant. pedida', digits=(16, 3))
    qty_recibida    = fields.Float('Cant. recibida', digits=(16, 3))
    qty_pendiente   = fields.Float('Cant. pendiente', digits=(16, 3))
    precio_unitario = fields.Float('Precio unit. (€)', digits=(16, 4))
    importe         = fields.Float('Importe pendiente (€)', digits=(16, 2))
    fecha_prevista  = fields.Date('Entrega prevista')


class LiraPurchasePending(models.TransientModel):
    _name = 'lira.purchase.pending'
    _description = 'Compras confirmadas pendientes de recibir'
    _rec_name = 'display_title'

    display_title   = fields.Char(default='Compras Pendientes de Recibir', readonly=True)
    total_pendiente = fields.Float('Total pendiente de recibir (€)', readonly=True)
    num_lineas      = fields.Integer('Líneas pendientes', readonly=True)
    num_proveedores = fields.Integer('Proveedores distintos', readonly=True)

    def _build_data(self):
        cid = self.env.company.id
        po_lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ['purchase', 'done']),
            ('order_id.company_id', '=', cid),
            ('product_qty', '>', 0),
        ])
        lines_data = []
        total = 0.0
        proveedores = set()
        for l in po_lines:
            pendiente = l.product_qty - l.qty_received
            if pendiente <= 0.001:
                continue
            importe = round(pendiente * l.price_unit, 2)
            total += importe
            partner = l.order_id.partner_id.commercial_partner_id
            proveedores.add(partner.id)
            fecha = None
            if hasattr(l, 'date_planned') and l.date_planned:
                fecha = l.date_planned.date() if hasattr(l.date_planned, 'date') else l.date_planned
            lines_data.append({
                'partner_id': partner.id,
                'pedido': l.order_id.name,
                'product_id': l.product_id.id if l.product_id else False,
                'categ_id': l.product_id.categ_id.id if l.product_id else False,
                'qty_pedida': l.product_qty,
                'qty_recibida': l.qty_received,
                'qty_pendiente': round(pendiente, 3),
                'precio_unitario': l.price_unit,
                'importe': importe,
                'fecha_prevista': fecha,
            })
        lines_data.sort(key=lambda x: -x['importe'])
        kpis = {
            'total_pendiente': round(total, 2),
            'num_lineas': len(lines_data),
            'num_proveedores': len(proveedores),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.purchase.pending.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_purchase_pending_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_purchase_pending_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Compras pendientes de recibir — detalle',
            'res_model': 'lira.purchase.pending.line', 'view_mode': 'list',
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
        return {'type': 'ir.actions.act_window', 'name': 'Compras Pendientes de Recibir',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
