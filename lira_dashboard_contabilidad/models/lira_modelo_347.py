from odoo import models, fields, api
from datetime import date
from collections import defaultdict


UMBRAL_347 = 3005.06  # €/año, umbral legal del modelo 347


class LiraModelo347Line(models.Model):
    _name = 'lira.modelo.347.line'
    _description = 'Línea Modelo 347 — operaciones con terceros'
    _order = 'total desc'

    user_id      = fields.Many2one('res.users', ondelete='cascade', index=True)
    partner_id   = fields.Many2one('res.partner', string='Tercero', index=True)
    partner_vat  = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    tipo_operacion = fields.Selection([
        ('venta',  'A — Ventas a cliente'),
        ('compra', 'B — Compras a proveedor'),
    ], string='Tipo operación', index=True)
    total        = fields.Float('Total anual (€)', digits=(16, 2))
    trim_1       = fields.Float('T1 (Ene–Mar) (€)', digits=(16, 2))
    trim_2       = fields.Float('T2 (Abr–Jun) (€)', digits=(16, 2))
    trim_3       = fields.Float('T3 (Jul–Sep) (€)', digits=(16, 2))
    trim_4       = fields.Float('T4 (Oct–Dic) (€)', digits=(16, 2))
    num_facturas = fields.Integer('Nº facturas')
    ejercicio    = fields.Integer('Ejercicio')

    def action_open_source(self):
        """Abre las facturas del tercero en el ejercicio."""
        self.ensure_one()
        move_type = ['out_invoice','out_refund'] if self.tipo_operacion == 'venta' else ['in_invoice','in_refund']
        return {
            'type': 'ir.actions.act_window',
            'name': f'Facturas {self.tipo_operacion} — {self.partner_id.name} ({self.ejercicio})',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', 'in', move_type),
                ('state', '=', 'posted'),
                ('partner_id.commercial_partner_id', '=', self.partner_id.id),
                ('invoice_date', '>=', f'{self.ejercicio}-01-01'),
                ('invoice_date', '<=', f'{self.ejercicio}-12-31'),
            ],
            'target': 'current',
        }


class LiraModelo347(models.TransientModel):
    _name = 'lira.modelo.347'
    _description = 'Modelo 347 — Operaciones con terceros'
    _rec_name = 'display_title'

    display_title = fields.Char(default='Modelo 347 — Operaciones con Terceros', readonly=True)

    ejercicio = fields.Integer('Ejercicio', default=lambda s: date.today().year)
    umbral    = fields.Float('Umbral legal (€)', default=UMBRAL_347, readonly=True)

    total_clientes       = fields.Float('Total clientes declarables (€)', readonly=True)
    total_proveedores    = fields.Float('Total proveedores declarables (€)', readonly=True)
    num_clientes         = fields.Integer('Clientes a declarar', readonly=True)
    num_proveedores      = fields.Integer('Proveedores a declarar', readonly=True)
    num_total_terceros   = fields.Integer('Terceros totales a declarar', readonly=True)

    # ───────────────────────────────────────────────────────────────────
    def _build_data(self):
        year = self.ejercicio or date.today().year
        cid = self.env.company.id
        dt_ini = f'{year}-01-01'
        dt_fin = f'{year}-12-31'

        # Facturas con IVA (solo operaciones que declara el 347: con impuestos,
        # nacionales, no intracomunitarias — aunque para simplificar incluimos todo
        # nacional y el contable afina después con filtros)
        facturas = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice','out_refund','in_invoice','in_refund']),
            ('invoice_date', '>=', dt_ini),
            ('invoice_date', '<=', dt_fin),
            ('company_id', '=', cid),
        ])

        groups = defaultdict(lambda: {
            'partner': None, 'tipo': '',
            'total': 0.0,
            'trim_1': 0.0, 'trim_2': 0.0, 'trim_3': 0.0, 'trim_4': 0.0,
            'facturas': 0,
        })
        for inv in facturas:
            if not inv.partner_id:
                continue
            cp = inv.partner_id.commercial_partner_id
            is_venta = inv.move_type in ('out_invoice','out_refund')
            sign = -1 if inv.move_type in ('out_refund','in_refund') else 1
            tipo = 'venta' if is_venta else 'compra'
            key = (cp.id, tipo)
            groups[key]['partner'] = cp
            groups[key]['tipo'] = tipo
            # Modelo 347: total = base + IVA (con IVA incluido)
            importe = sign * (inv.amount_total_signed if hasattr(inv, 'amount_total_signed') else inv.amount_total)
            groups[key]['total'] += importe
            groups[key]['facturas'] += 1
            if inv.invoice_date:
                m = inv.invoice_date.month
                if m <= 3: groups[key]['trim_1'] += importe
                elif m <= 6: groups[key]['trim_2'] += importe
                elif m <= 9: groups[key]['trim_3'] += importe
                else: groups[key]['trim_4'] += importe

        # Filtrar solo los que superan umbral
        lines_data = []
        total_cli = total_prov = 0.0
        cnt_cli = cnt_prov = 0
        for (pid, tipo), g in groups.items():
            if abs(g['total']) < UMBRAL_347:
                continue
            lines_data.append({
                'partner_id': pid,
                'tipo_operacion': tipo,
                'total':        round(g['total'], 2),
                'trim_1':       round(g['trim_1'], 2),
                'trim_2':       round(g['trim_2'], 2),
                'trim_3':       round(g['trim_3'], 2),
                'trim_4':       round(g['trim_4'], 2),
                'num_facturas': g['facturas'],
                'ejercicio':    year,
            })
            if tipo == 'venta':
                total_cli += g['total']; cnt_cli += 1
            else:
                total_prov += g['total']; cnt_prov += 1

        lines_data.sort(key=lambda x: -abs(x['total']))
        kpis = {
            'total_clientes':     round(total_cli, 2),
            'total_proveedores':  round(total_prov, 2),
            'num_clientes':       cnt_cli,
            'num_proveedores':    cnt_prov,
            'num_total_terceros': cnt_cli + cnt_prov,
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.modelo.347.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    @api.onchange('ejercicio')
    def _onchange_ejercicio(self):
        self._compute_kpis_only()

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_modelo_347_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_modelo_347_line_search', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window', 'name': 'Modelo 347 — detalle por tercero',
            'res_model': 'lira.modelo.347.line', 'view_mode': 'list',
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
        rec = self.create({'ejercicio': date.today().year})
        rec._compute_kpis_only()
        return {'type': 'ir.actions.act_window', 'name': 'Modelo 347',
                'res_model': self._name, 'res_id': rec.id,
                'view_mode': 'form', 'target': 'current'}
