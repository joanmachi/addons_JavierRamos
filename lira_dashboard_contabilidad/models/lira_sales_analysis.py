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
    num_facturas = fields.Integer('Documentos')
    ticket_medio = fields.Float('Ticket medio (€)', digits=(16, 2))
    ultima_fecha = fields.Date('Última fecha')
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
    kpi_fuente        = fields.Char('Fuente')

    def action_open_source(self):
        """Abre los documentos origen (pedidos de venta o facturas) filtrados
        según la dimensión de agrupación y el periodo."""
        self.ensure_one()
        ag = self.kpi_agrupar_por or ''

        # Resolver el registro de la dimensión a partir de la etiqueta de la fila.
        prod = partner = cat = sp = False
        if ag == 'product':
            prod = self.env['product.product'].search([('display_name', '=', self.label)], limit=1)
        elif ag == 'customer':
            partner = self.env['res.partner'].search([('name', '=', self.label)], limit=1)
        elif ag == 'category':
            cat = self.env['product.category'].search([('name', '=', self.label)], limit=1)
        elif ag == 'salesperson':
            sp = self.env['res.users'].search([('name', '=', self.label)], limit=1)

        if self.kpi_fuente == 'facturas':
            domain = [
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
            ]
            if self.kpi_date_from:
                domain.append(('invoice_date', '>=', self.kpi_date_from))
            if self.kpi_date_to:
                domain.append(('invoice_date', '<=', self.kpi_date_to))
            name = 'Facturas de cliente'
            if prod:
                domain.append(('invoice_line_ids.product_id', '=', prod.id))
                name = f'Facturas con producto — {self.label}'
            elif partner:
                domain.append(('partner_id.commercial_partner_id', '=', partner.commercial_partner_id.id))
                name = f'Facturas — {self.label}'
            elif cat:
                domain.append(('invoice_line_ids.product_id.categ_id', '=', cat.id))
                name = f'Facturas categoría — {self.label}'
            elif sp:
                domain.append(('invoice_user_id', '=', sp.id))
                name = f'Facturas vendedor — {self.label}'
            return {
                'type': 'ir.actions.act_window', 'name': name,
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': domain, 'target': 'current',
                'context': {'default_move_type': 'out_invoice'},
            }

        # Fuente = pedidos de venta
        domain = [('state', 'in', ['sale', 'done'])]
        if self.kpi_date_from:
            domain.append(('date_order', '>=', self.kpi_date_from))
        if self.kpi_date_to:
            domain.append(('date_order', '<=', str(self.kpi_date_to) + ' 23:59:59'))
        name = 'Pedidos de venta'
        if prod:
            domain.append(('order_line.product_id', '=', prod.id))
            name = f'Pedidos con producto — {self.label}'
        elif partner:
            domain.append(('partner_id.commercial_partner_id', '=', partner.commercial_partner_id.id))
            name = f'Pedidos — {self.label}'
        elif cat:
            domain.append(('order_line.product_id.categ_id', '=', cat.id))
            name = f'Pedidos categoría — {self.label}'
        elif sp:
            domain.append(('user_id', '=', sp.id))
            name = f'Pedidos vendedor — {self.label}'
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
    fuente      = fields.Selection([
        ('pedidos',  'Ventas (pedidos confirmados)'),
        ('facturas', 'Facturación (facturas emitidas)'),
    ], default='pedidos', required=True, string='Fuente')
    agrupar_por = fields.Selection([
        ('product',     'Por producto'),
        ('customer',    'Por cliente'),
        ('category',    'Por categoría'),
        ('month',       'Por mes'),
        ('salesperson', 'Por vendedor'),
    ], default='product', required=True, string='Agrupar por')

    total_ventas  = fields.Float('Total (€)', readonly=True)
    num_clientes  = fields.Integer('Clientes activos', readonly=True)
    num_productos = fields.Integer('Productos', readonly=True)
    top_producto  = fields.Char('Mejor producto', readonly=True)
    top_cliente   = fields.Char('Mejor cliente', readonly=True)

    def _collect(self, rec):
        """Recopila y normaliza los movimientos (pedidos o facturas) en una
        estructura común y los agrupa según la dimensión elegida.

        Devuelve: (groups, num_clientes, num_productos, cli_groups)
        - groups: {key: {label, importe, qty, docs(set), fechas[]}}
        - cli_groups: {nombre_cliente: importe}  (para hallar el top cliente)
        """
        df = rec.date_from or date.today().replace(month=1, day=1)
        dt = rec.date_to   or date.today()
        company = self.env.company

        movimientos = []
        if rec.fuente == 'facturas':
            # Facturas y rectificativas de cliente, contabilizadas.
            # Solo líneas de producto (display_type='product'): excluye
            # secciones, notas, impuestos y términos de pago.
            mls = self.env['account.move.line'].search([
                ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                ('move_id.state',     '=',  'posted'),
                ('display_type',      '=',  'product'),
                ('move_id.invoice_date', '>=', str(df)),
                ('move_id.invoice_date', '<=', str(dt)),
                ('company_id',        '=',  company.id),
            ])
            for l in mls:
                mv = l.move_id
                # La rectificativa (abono) resta de las ventas netas.
                sign = -1.0 if mv.move_type == 'out_refund' else 1.0
                movimientos.append({
                    'importe':     l.price_subtotal * sign,
                    'qty':         l.quantity * sign,
                    'fecha':       mv.invoice_date,
                    'product':     l.product_id,
                    'partner':     mv.partner_id.commercial_partner_id,
                    'salesperson': mv.invoice_user_id,
                    'doc_id':      mv.id,
                })
        else:
            # Pedidos de venta confirmados.
            sols = self.env['sale.order.line'].search([
                ('order_id.state',      'in', ['sale', 'done']),
                ('order_id.date_order', '>=', str(df)),
                ('order_id.date_order', '<=', str(dt) + ' 23:59:59'),
                ('order_id.company_id', '=',  company.id),
            ])
            for l in sols:
                o = l.order_id
                movimientos.append({
                    'importe':     l.price_subtotal,
                    'qty':         l.product_uom_qty,
                    'fecha':       o.date_order.date() if o.date_order else False,
                    'product':     l.product_id,
                    'partner':     o.partner_id.commercial_partner_id,
                    'salesperson': o.user_id,
                    'doc_id':      o.id,
                })

        groups = defaultdict(lambda: {
            'label': '', 'importe': 0.0, 'qty': 0.0, 'docs': set(), 'fechas': [],
        })
        clientes  = set()
        productos = set()
        cli_groups = defaultdict(float)

        for m in movimientos:
            ag = rec.agrupar_por
            if ag == 'product':
                if not m['product']:
                    continue
                key, label = m['product'].id, (m['product'].display_name or '—')
            elif ag == 'customer':
                key, label = m['partner'].id, (m['partner'].name or '—')
            elif ag == 'category':
                cat = m['product'].categ_id if m['product'] else False
                key, label = (cat.id if cat else 0), (cat.name if cat else 'Sin categoría')
            elif ag == 'month':
                if not m['fecha']:
                    continue
                key, label = m['fecha'].strftime('%Y-%m'), m['fecha'].strftime('%b %Y')
            elif ag == 'salesperson':
                sp = m['salesperson']
                key, label = (sp.id if sp else 0), (sp.name if sp else 'Sin asignar')
            else:
                continue

            g = groups[key]
            g['label']    = label
            g['importe'] += m['importe']
            g['qty']     += m['qty']
            g['docs'].add(m['doc_id'])
            if m['fecha']:
                g['fechas'].append(m['fecha'])

            if m['partner']:
                clientes.add(m['partner'].id)
                cli_groups[m['partner'].name] += m['importe']
            if m['product']:
                productos.add(m['product'].id)

        return groups, len(clientes), len(productos), cli_groups

    def _compute_and_store(self):
        """Calcula los datos y los guarda en lira.sales.line del usuario actual."""
        for rec in self:
            df = rec.date_from or date.today().replace(month=1, day=1)
            dt = rec.date_to   or date.today()

            groups, num_clientes, num_productos, cli_groups = rec._collect(rec)
            total_v = sum(g['importe'] for g in groups.values())

            result = []
            for key, g in sorted(groups.items(), key=lambda x: -x[1]['importe']):
                if g['importe'] <= 0:
                    continue
                n_doc  = len(g['docs'])
                ticket = round(g['importe'] / n_doc, 2) if n_doc else 0.0
                pct_v  = round(g['importe'] / total_v * 100, 1) if total_v else 0.0
                ultima = max(g['fechas']) if g['fechas'] else False
                result.append({
                    'label':        g['label'],
                    'qty':          g['qty'],
                    'importe':      g['importe'],
                    'num_facturas': n_doc,
                    'ticket_medio': ticket,
                    'ultima_fecha': ultima,
                    'pct_ventas':   pct_v,
                })

            acum = 0.0
            for r in result:
                acum += r['importe']
                pct_acum = acum / total_v * 100 if total_v else 0
                r['abc'] = 'A' if pct_acum <= 80 else ('B' if pct_acum <= 95 else 'C')

            top_producto = result[0]['label'] if result else '—'
            top_cliente  = max(cli_groups, key=cli_groups.get) if cli_groups else '—'

            # Actualizar KPIs en el wizard
            rec.total_ventas  = total_v
            rec.num_clientes  = num_clientes
            rec.num_productos = num_productos
            rec.top_producto  = top_producto
            rec.top_cliente   = top_cliente

            # Borrar líneas anteriores del usuario y escribir las nuevas
            SalesLine = self.env['lira.sales.line']
            SalesLine.search([('user_id', '=', self.env.user.id)]).unlink()

            kpi_vals = {
                'user_id':           self.env.user.id,
                'kpi_total_ventas':  total_v,
                'kpi_num_clientes':  num_clientes,
                'kpi_num_productos': num_productos,
                'kpi_top_producto':  top_producto,
                'kpi_top_cliente':   top_cliente,
                'kpi_date_from':     df,
                'kpi_date_to':       dt,
                'kpi_agrupar_por':   rec.agrupar_por,
                'kpi_fuente':        rec.fuente,
            }
            for i, r in enumerate(result, 1):
                SalesLine.create({**r, 'rank': i, **kpi_vals})

    @api.onchange('date_from', 'date_to', 'agrupar_por', 'fuente')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def _compute_kpis_only(self):
        """Calcula solo los KPIs del wizard (sin escribir líneas en DB)."""
        for rec in self:
            groups, num_clientes, num_productos, cli_groups = rec._collect(rec)

            rec.total_ventas  = sum(g['importe'] for g in groups.values())
            rec.num_clientes  = num_clientes
            rec.num_productos = num_productos

            # Mejor producto: agrupar por producto independientemente de la dimensión.
            if rec.agrupar_por == 'product' and groups:
                top = max(groups.values(), key=lambda g: g['importe'])
                rec.top_producto = top['label']
            else:
                rec.top_producto = '—'
            rec.top_cliente = max(cli_groups, key=cli_groups.get) if cli_groups else '—'

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
        titulo = 'Análisis de Facturación — Ranking' if self.fuente == 'facturas' \
            else 'Análisis de Ventas — Ranking'
        action = {
            'type':      'ir.actions.act_window',
            'name':      titulo,
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
