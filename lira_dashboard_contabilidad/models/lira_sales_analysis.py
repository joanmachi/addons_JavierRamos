from odoo import models, fields, api
from datetime import date
from collections import defaultdict


class LiraSalesLine(models.Model):
    _name = 'lira.sales.line'
    _description = 'Línea análisis de ventas'
    _order = 'rank'

    user_id      = fields.Many2one('res.users', ondelete='cascade', index=True)
    rank         = fields.Integer('Pos.')
    label        = fields.Char('Nombre')
    qty          = fields.Float('Uds.', digits=(16, 2))
    importe      = fields.Float('Ventas (€)', digits=(16, 2))
    num_facturas = fields.Integer('Pedidos')
    ticket_medio = fields.Float('Ticket medio (€)', digits=(16, 2))
    ultima_fecha = fields.Date('Último pedido')
    pct_ventas   = fields.Float('% s/total', digits=(16, 1))
    abc          = fields.Char('ABC')
    # KPIs compartidos (mismo valor en todas las líneas de la sesión)
    kpi_total_ventas  = fields.Float('Total ventas', digits=(16, 2))
    kpi_num_clientes  = fields.Integer('Clientes activos')
    kpi_num_productos = fields.Integer('Productos vendidos')
    kpi_top_producto  = fields.Char('Top producto')
    kpi_top_cliente   = fields.Char('Top cliente')
    kpi_date_from     = fields.Date('Desde')
    kpi_date_to       = fields.Date('Hasta')
    kpi_agrupar_por   = fields.Char('Agrupación')

    def action_open_source(self):
        """Abre pedidos de venta filtrados según la dimensión de agrupación y periodo."""
        self.ensure_one()
        domain = [('state', 'in', ['sale','done'])]
        if self.kpi_date_from:
            domain.append(('date_order','>=',self.kpi_date_from))
        if self.kpi_date_to:
            domain.append(('date_order','<=',str(self.kpi_date_to) + ' 23:59:59'))
        name = 'Pedidos de venta'
        ag = self.kpi_agrupar_por or ''
        if ag == 'product':
            prod = self.env['product.product'].search([('display_name','=',self.label)], limit=1)
            if prod:
                domain.append(('order_line.product_id','=',prod.id))
                name = f'Pedidos con producto — {self.label}'
        elif ag in ('customer','partner','cliente'):
            partner = self.env['res.partner'].search([('name','=',self.label)], limit=1)
            if partner:
                domain.append(('partner_id.commercial_partner_id','=',partner.commercial_partner_id.id))
                name = f'Pedidos — {self.label}'
        elif ag in ('category','categoria'):
            cat = self.env['product.category'].search([('name','=',self.label)], limit=1)
            if cat:
                domain.append(('order_line.product_id.categ_id','=',cat.id))
                name = f'Pedidos categoría — {self.label}'
        return {
            'type': 'ir.actions.act_window', 'name': name,
            'res_model': 'sale.order', 'view_mode': 'list,form',
            'domain': domain, 'target': 'current',
        }


class LiraSalesAnalysis(models.TransientModel):
    _name = 'lira.sales.analysis'
    _description = 'Análisis exhaustivo de ventas'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Análisis de Ventas', readonly=True)

    date_from   = fields.Date('Desde', default=lambda s: date.today().replace(month=1, day=1))
    date_to     = fields.Date('Hasta', default=fields.Date.today)
    agrupar_por = fields.Selection([
        ('product',     'Por producto'),
        ('customer',    'Por cliente'),
        ('category',    'Por categoría'),
        ('month',       'Por mes'),
        ('salesperson', 'Por vendedor'),
    ], default='product', required=True, string='Agrupar por')

    total_ventas  = fields.Float('Total ventas (€)', readonly=True)
    num_clientes  = fields.Integer('Clientes activos', readonly=True)
    num_productos = fields.Integer('Productos vendidos', readonly=True)
    top_producto  = fields.Char('Mejor producto', readonly=True)
    top_cliente   = fields.Char('Mejor cliente', readonly=True)

    def _compute_and_store(self):
        """Calcula los datos y los guarda en lira.sales.line del usuario actual."""
        for rec in self:
            df = rec.date_from or date.today().replace(month=1, day=1)
            dt = rec.date_to   or date.today()

            lines = self.env['sale.order.line'].search([
                ('order_id.state',      'in', ['sale', 'done']),
                ('order_id.date_order', '>=', str(df)),
                ('order_id.date_order', '<=', str(dt) + ' 23:59:59'),
                ('order_id.company_id', '=',  self.env.company.id),
            ])

            groups = defaultdict(lambda: {
                'label': '', 'importe': 0.0, 'qty': 0.0,
                'pedidos': set(), 'fechas': [],
            })

            for l in lines:
                order = l.order_id
                if rec.agrupar_por == 'product':
                    if not l.product_id:
                        continue
                    key = l.product_id.id
                    groups[key]['label'] = l.product_id.display_name or '—'
                elif rec.agrupar_por == 'customer':
                    cp = order.partner_id.commercial_partner_id
                    key = cp.id
                    groups[key]['label'] = cp.name or '—'
                elif rec.agrupar_por == 'category':
                    cat = l.product_id.categ_id if l.product_id else False
                    key = cat.id if cat else 0
                    groups[key]['label'] = cat.name if cat else 'Sin categoría'
                elif rec.agrupar_por == 'month':
                    if order.date_order:
                        key = order.date_order.strftime('%Y-%m')
                        groups[key]['label'] = order.date_order.strftime('%b %Y')
                    else:
                        continue
                elif rec.agrupar_por == 'salesperson':
                    sp = order.user_id
                    key = sp.id if sp else 0
                    groups[key]['label'] = sp.name if sp else 'Sin asignar'

                groups[key]['importe'] += l.price_subtotal
                groups[key]['qty']     += l.product_uom_qty
                groups[key]['pedidos'].add(order.id)
                if order.date_order:
                    groups[key]['fechas'].append(order.date_order.date())

            total_v = sum(g['importe'] for g in groups.values())

            result = []
            for key, g in sorted(groups.items(), key=lambda x: -x[1]['importe']):
                if g['importe'] <= 0:
                    continue
                n_ped  = len(g['pedidos'])
                ticket = round(g['importe'] / n_ped, 2) if n_ped else 0.0
                pct_v  = round(g['importe'] / total_v * 100, 1) if total_v else 0.0
                ultima = max(g['fechas']) if g['fechas'] else False
                result.append({
                    'label':        g['label'],
                    'qty':          g['qty'],
                    'importe':      g['importe'],
                    'num_facturas': n_ped,
                    'ticket_medio': ticket,
                    'ultima_fecha': ultima,
                    'pct_ventas':   pct_v,
                })

            acum = 0.0
            for r in result:
                acum += r['importe']
                pct_acum = acum / total_v * 100 if total_v else 0
                r['abc'] = 'A' if pct_acum <= 80 else ('B' if pct_acum <= 95 else 'C')

            num_clientes  = len(set(l.order_id.partner_id.commercial_partner_id.id for l in lines))
            num_productos = len(set(l.product_id.id for l in lines if l.product_id))
            top_producto  = result[0]['label'] if result else '—'

            cli_groups = defaultdict(float)
            for l in lines:
                cp = l.order_id.partner_id.commercial_partner_id
                cli_groups[cp.name] += l.price_subtotal
            top_cliente = max(cli_groups, key=cli_groups.get) if cli_groups else '—'

            # Actualizar KPIs en el wizard
            rec.total_ventas  = total_v
            rec.num_clientes  = num_clientes
            rec.num_productos = num_productos
            rec.top_producto  = top_producto
            rec.top_cliente   = top_cliente

            # Borrar líneas anteriores del usuario y escribir las nuevas
            SalesLine = self.env['lira.sales.line']
            SalesLine.search([('user_id', '=', self.env.user.id)]).unlink()

            agrupar_label = dict(rec._fields['agrupar_por'].selection).get(rec.agrupar_por, '')
            kpi_vals = {
                'user_id':           self.env.user.id,
                'kpi_total_ventas':  total_v,
                'kpi_num_clientes':  num_clientes,
                'kpi_num_productos': num_productos,
                'kpi_top_producto':  top_producto,
                'kpi_top_cliente':   top_cliente,
                'kpi_date_from':     df,
                'kpi_date_to':       dt,
                'kpi_agrupar_por':   agrupar_label,
            }
            for i, r in enumerate(result, 1):
                SalesLine.create({**r, 'rank': i, **kpi_vals})

    @api.onchange('date_from', 'date_to', 'agrupar_por')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def _compute_kpis_only(self):
        """Calcula solo los KPIs del wizard (sin escribir líneas en DB)."""
        for rec in self:
            df = rec.date_from or date.today().replace(month=1, day=1)
            dt = rec.date_to   or date.today()

            lines = self.env['sale.order.line'].search([
                ('order_id.state',      'in', ['sale', 'done']),
                ('order_id.date_order', '>=', str(df)),
                ('order_id.date_order', '<=', str(dt) + ' 23:59:59'),
                ('order_id.company_id', '=',  self.env.company.id),
            ])

            total_v = sum(l.price_subtotal for l in lines)
            rec.total_ventas  = total_v
            rec.num_clientes  = len(set(l.order_id.partner_id.commercial_partner_id.id for l in lines))
            rec.num_productos = len(set(l.product_id.id for l in lines if l.product_id))

            by_product = defaultdict(float)
            by_client  = defaultdict(float)
            for l in lines:
                if l.product_id:
                    by_product[l.product_id.display_name] += l.price_subtotal
                cp = l.order_id.partner_id.commercial_partner_id
                by_client[cp.name] += l.price_subtotal

            rec.top_producto = max(by_product, key=by_product.get) if by_product else '—'
            rec.top_cliente  = max(by_client,  key=by_client.get)  if by_client  else '—'

    def action_ver_ranking(self):
        """Calcula, guarda en DB y abre la lista de lira.sales.line."""
        self.ensure_one()
        self._compute_and_store()
        return self._build_list_action()

    def action_refresh(self):
        self.ensure_one()
        self._compute_and_store()
        return self._build_list_action()

    def _build_list_action(self):
        search_view = self.env.ref(
            'lira_dashboard_contabilidad.view_lira_sales_line_search', raise_if_not_found=False
        )
        list_view = self.env.ref(
            'lira_dashboard_contabilidad.view_lira_sales_line_list2', raise_if_not_found=False
        )
        action = {
            'type':      'ir.actions.act_window',
            'name':      'Análisis de Ventas — Ranking',
            'res_model': 'lira.sales.line',
            'view_mode': 'list',
            'domain':    [('user_id', '=', self.env.user.id)],
            'context':   {'create': False, 'delete': False},
        }
        if search_view:
            action['search_view_id'] = [search_view.id, 'search']
        if list_view:
            action['views'] = [(list_view.id, 'list')]
        return action

    @api.model
    def action_open(self):
        rec = self.create({
            'date_from': date.today().replace(month=1, day=1),
            'date_to':   date.today(),
        })
        rec._compute_kpis_only()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Análisis de Ventas',
            'res_model': self._name,
            'res_id':    rec.id,
            'view_mode': 'form',
            'target':    'current',
        }
