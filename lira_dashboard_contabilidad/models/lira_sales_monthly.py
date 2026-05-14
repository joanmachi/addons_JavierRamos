from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta


class LiraSalesMonthlyLine(models.Model):
    _name = 'lira.sales.monthly.line'
    _description = 'Línea pedidos confirmados por mes'
    _order = 'mes desc'

    def action_open_source(self):
        """Abre pedidos de venta del mes."""
        self.ensure_one()
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        try:
            dt_ini = datetime.strptime(self.mes, '%b %Y')
        except Exception:
            try:
                dt_ini = datetime.strptime(self.mes, '%Y-%m')
            except Exception:
                return False
        dt_ini = dt_ini.replace(day=1).date()
        dt_fin = dt_ini + relativedelta(months=1) - relativedelta(days=1)
        return {
            'type': 'ir.actions.act_window',
            'name': f'Pedidos de venta — {self.mes}',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [
                ('state', 'in', ['sale','done']),
                ('date_order', '>=', dt_ini),
                ('date_order', '<=', str(dt_fin) + ' 23:59:59'),
            ],
            'target': 'current',
        }

    user_id       = fields.Many2one('res.users', ondelete='cascade', index=True)
    mes           = fields.Char('Mes')
    num_pedidos   = fields.Integer('Pedidos')
    total_neto    = fields.Float('Importe neto (€)', digits=(16, 2))
    ticket_medio  = fields.Float('Ticket medio (€)', digits=(16, 2))
    variacion_pct = fields.Float('Var. % vs mes ant.', digits=(16, 1))
    es_mejor_mes  = fields.Boolean('Mejor mes')


class LiraSalesMonthly(models.TransientModel):
    _name = 'lira.sales.monthly'
    _description = 'Pedidos confirmados por mes'
    _rec_name = 'display_title'

    display_title     = fields.Char(default='Pedidos Confirmados por Mes', readonly=True)
    periodos          = fields.Integer('Meses a mostrar', default=12)
    total_pedidos     = fields.Integer('Total pedidos', readonly=True)
    total_importe     = fields.Float('Total importe neto (€)', readonly=True)
    media_mensual     = fields.Float('Media mensual (€)', readonly=True)
    mejor_mes         = fields.Char('Mejor mes', readonly=True)
    peor_mes          = fields.Char('Mes más bajo', readonly=True)
    meses_sin_pedidos = fields.Integer('Meses sin pedidos', readonly=True)

    def _build_data(self):
        rec = self
        today = date.today()
        n = max(rec.periodos, 1)
        cid = self.env.company.id
        importes_mensuales = []
        for i in range(n - 1, -1, -1):
            mes_ini = (today - relativedelta(months=i)).replace(day=1)
            mes_fin = mes_ini + relativedelta(months=1) - relativedelta(days=1)
            mes_label = mes_ini.strftime('%b %Y')
            orders = self.env['sale.order'].search([
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', mes_ini.strftime('%Y-%m-%d')),
                ('date_order', '<=', mes_fin.strftime('%Y-%m-%d') + ' 23:59:59'),
                ('company_id', '=', cid),
            ])
            num = len(orders)
            neto = round(sum(o.amount_untaxed for o in orders), 2)
            ticket = round(neto / num, 2) if num else 0.0
            importes_mensuales.append((mes_label, num, neto, ticket))
        lines_data = []
        for idx, (mes_label, num, neto, ticket) in enumerate(importes_mensuales):
            if idx == 0 or importes_mensuales[idx - 1][2] == 0:
                variacion = 0.0
            else:
                prev = importes_mensuales[idx - 1][2]
                variacion = round((neto - prev) / prev * 100, 1)
            lines_data.append({
                'mes': mes_label, 'num_pedidos': num, 'total_neto': neto,
                'ticket_medio': ticket, 'variacion_pct': variacion, 'es_mejor_mes': False,
            })
        meses_con_datos = [d for d in lines_data if d['total_neto'] > 0]
        if meses_con_datos:
            max_neto = max(d['total_neto'] for d in meses_con_datos)
            for d in lines_data:
                if d['total_neto'] == max_neto:
                    d['es_mejor_mes'] = True
                    break
        total_ped = sum(d['num_pedidos'] for d in lines_data)
        total_imp = round(sum(d['total_neto'] for d in lines_data), 2)
        meses_cnt = sum(1 for d in lines_data if d['total_neto'] > 0)
        kpis = {
            'total_pedidos': total_ped,
            'total_importe': total_imp,
            'media_mensual': round(total_imp / meses_cnt, 2) if meses_cnt else 0.0,
            'meses_sin_pedidos': sum(1 for d in lines_data if d['num_pedidos'] == 0),
            'mejor_mes': max(meses_con_datos, key=lambda d: d['total_neto'])['mes'] if meses_con_datos else '—',
            'peor_mes': min(meses_con_datos, key=lambda d: d['total_neto'])['mes'] if meses_con_datos else '—',
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.sales.monthly.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_sales_monthly_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_sales_monthly_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Evolución mensual — detalle',
            'res_model': 'lira.sales.monthly.line', 'view_mode': 'list',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'create': False, 'delete': False},
        }
        if lv: action['views'] = [(lv.id, 'list')]
        if sv: action['search_view_id'] = [sv.id, 'search']
        return action

    @api.onchange('periodos')
    def _onchange_compute(self):
        self._compute_kpis_only()

    def action_refresh(self):
        self._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def action_open(self):
        rec = self.create({})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Pedidos Confirmados por Mes',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
