from odoo import models, fields, api
from datetime import date


class LiraCollectionsLine(models.Model):
    _name = 'lira.collections.line'
    _description = 'Línea cobros y pagos pendientes'
    _order = 'dias_vencido desc'

    def action_open_source(self):
        """Abre la factura original en Odoo."""
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    user_id          = fields.Many2one('res.users', ondelete='cascade', index=True)
    tipo             = fields.Selection([('cobro', 'Cobro'), ('pago', 'Pago')], string='Tipo', index=True)
    partner_id       = fields.Many2one('res.partner', string='Empresa', index=True)
    partner_vat      = fields.Char(related='partner_id.vat', string='NIF/CIF', store=False)
    partner_city     = fields.Char(related='partner_id.city', string='Ciudad', store=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', string='País', store=False)
    partner_ref      = fields.Char(related='partner_id.ref', string='Ref. empresa', store=False)
    partner_email    = fields.Char(related='partner_id.email', string='Email', store=False)
    move_id          = fields.Many2one('account.move', string='Factura')
    referencia       = fields.Char('Referencia')
    fecha_factura    = fields.Date('Fecha factura')
    fecha_vencimiento = fields.Date('Vencimiento')
    importe_original = fields.Float('Importe total (€)', digits=(16, 2))
    importe_pendiente = fields.Float('Pendiente (€)', digits=(16, 2))
    dias_vencido     = fields.Integer('Días vencido')
    estado           = fields.Selection([
        ('ok',      'No vencido'),
        ('leve',    'Vencido 1–30 d'),
        ('medio',   'Vencido 31–60 d'),
        ('grave',   'Vencido 61–90 d'),
        ('critico', 'Vencido +90 d'),
    ], string='Estado', index=True)


class LiraCollections(models.TransientModel):
    _name = 'lira.collections'
    _description = 'Panel de cobros y pagos pendientes'
    _rec_name = 'display_title'

    display_title      = fields.Char(default='Cobros y Pagos Pendientes', readonly=True)
    total_cobrar       = fields.Float('Total a cobrar (€)', readonly=True)
    total_pagar        = fields.Float('Total a pagar (€)', readonly=True)
    saldo_neto         = fields.Float('Saldo neto (€)', readonly=True)
    vencido_cobrar     = fields.Float('Vencido a cobrar (€)', readonly=True)
    vencido_pagar      = fields.Float('Vencido a pagar (€)', readonly=True)
    critico_cobrar     = fields.Float('+90 días a cobrar (€)', readonly=True)
    num_facturas_cobro = fields.Integer('Facturas pendientes cobro', readonly=True)
    num_facturas_pago  = fields.Integer('Facturas pendientes pago', readonly=True)

    def _build_data(self):
        today = date.today()
        lines_data = []
        for move_type, tipo in [('out_invoice', 'cobro'), ('in_invoice', 'pago')]:
            movs = self.env['account.move'].search([
                ('move_type', '=', move_type),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('company_id', '=', self.env.company.id),
            ])
            for inv in movs:
                due = inv.invoice_date_due
                dias = (today - due).days if due else 0
                estado = ('critico' if dias > 90 else 'grave' if dias > 60 else
                          'medio' if dias > 30 else 'leve' if dias > 0 else 'ok')
                lines_data.append({
                    'tipo': tipo,
                    'partner_id':        inv.partner_id.commercial_partner_id.id,
                    'move_id':           inv.id,
                    'referencia':        inv.name,
                    'fecha_factura':     inv.invoice_date,
                    'fecha_vencimiento': due,
                    'importe_original':  inv.amount_total,
                    'importe_pendiente': inv.amount_residual,
                    'dias_vencido':      dias,
                    'estado':            estado,
                })
        lines_data.sort(key=lambda x: -x['dias_vencido'])
        cobros = [d for d in lines_data if d['tipo'] == 'cobro']
        pagos  = [d for d in lines_data if d['tipo'] == 'pago']
        kpis = {
            'total_cobrar':       round(sum(d['importe_pendiente'] for d in cobros), 2),
            'total_pagar':        round(sum(d['importe_pendiente'] for d in pagos), 2),
            'saldo_neto':         round(sum(d['importe_pendiente'] for d in cobros) - sum(d['importe_pendiente'] for d in pagos), 2),
            'vencido_cobrar':     round(sum(d['importe_pendiente'] for d in cobros if d['dias_vencido'] > 0), 2),
            'vencido_pagar':      round(sum(d['importe_pendiente'] for d in pagos  if d['dias_vencido'] > 0), 2),
            'critico_cobrar':     round(sum(d['importe_pendiente'] for d in cobros if d['dias_vencido'] > 90), 2),
            'num_facturas_cobro': len(cobros),
            'num_facturas_pago':  len(pagos),
        }
        return lines_data, kpis

    def _compute_kpis_only(self):
        for rec in self:
            _, kpis = rec._build_data()
            rec.write(kpis)

    def _compute_and_store(self):
        for rec in self:
            lines_data, kpis = rec._build_data()
            Line = self.env['lira.collections.line']
            Line.search([('user_id', '=', self.env.user.id)]).unlink()
            uid = self.env.user.id
            for d in lines_data:
                Line.create({**d, 'user_id': uid})
            rec.write(kpis)

    def action_ver_tabla(self):
        self.ensure_one()
        self._compute_and_store()
        lv = self.env.ref('lira_dashboard_contabilidad.view_lira_collections_line_list', raise_if_not_found=False)
        sv = self.env.ref('lira_dashboard_contabilidad.view_lira_collections_line_search', raise_if_not_found=False)
        action = {
            'type':      'ir.actions.act_window',
            'name':      'Cobros y pagos pendientes — detalle',
            'res_model': 'lira.collections.line',
            'view_mode': 'list',
            'domain':    [('user_id', '=', self.env.user.id)],
            'context':   {'create': False, 'delete': False},
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
        return {
            'type': 'ir.actions.act_window', 'name': 'Cobros y Pagos Pendientes',
            'res_model': self._name, 'res_id': rec.id,
            'view_mode': 'form', 'target': 'current',
        }
