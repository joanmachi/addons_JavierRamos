from odoo import api, fields, models
from datetime import datetime
import math


class LiraSupervisorWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    lira_validation_state = fields.Selection([
        ('waiting',   'Esperando fase anterior'),
        ('idle',      'Disponible — sin operario'),
        ('working',   'En proceso'),
        ('pending',   'Pendiente de validar'),
        ('validated', 'Completada'),
    ], string='Estado supervisión',
       compute='_compute_lira_validation_state',
       store=True)

    lira_date_ready      = fields.Datetime(string='Entregado el', readonly=True)
    lira_waiting_minutes = fields.Integer(string='Espera (min)', compute='_compute_lira_waiting_minutes')
    lira_supervisor_note = fields.Char(string='Motivo rechazo')
    lira_validated_by    = fields.Many2one('res.users', string='Validado por', readonly=True)
    lira_validated_date  = fields.Datetime(string='Validado el', readonly=True)
    lira_rejection_date  = fields.Datetime(string='Rechazado el', readonly=True)
    lira_production_seq      = fields.Char(string='Nº Orden', compute='_compute_lira_production_seq')
    lira_requested_by_names  = fields.Char(string='Solicitado por', readonly=True)
    lira_qty_progress        = fields.Char(string='Val./Total', compute='_compute_lira_qty_progress')

    @api.depends('production_id.name')
    def _compute_lira_production_seq(self):
        for wo in self:
            name = wo.production_id.name or ''
            wo.lira_production_seq = name.rsplit('/', 1)[-1] if '/' in name else name

    @api.depends('qty_validated', 'qty_production')
    def _compute_lira_qty_progress(self):
        for wo in self:
            validated = int(round(wo.qty_validated or 0))
            total = int(round(wo.qty_production or 0))
            wo.lira_qty_progress = f"{validated}/{total}"

    @api.depends(
        'qty_ready_to_validate',
        'employee_ids',
        'qty_validated',
        'production_id.workorder_ids.qty_validated',
        'production_id.product_qty',
        'state',
    )
    def _compute_lira_validation_state(self):
        for wo in self:
            if wo.state in ('done', 'cancel'):
                wo.lira_validation_state = 'validated'
            elif wo.qty_ready_to_validate > 0:
                wo.lira_validation_state = 'pending'
            elif wo.employee_ids:
                wo.lira_validation_state = 'working'
            else:
                prev = wo.prev_validated_qty
                if prev > 0:
                    wo.lira_validation_state = 'idle'
                elif wo.qty_validated > 0:
                    wo.lira_validation_state = 'validated'
                else:
                    wo.lira_validation_state = 'waiting'

    @api.depends('lira_date_ready', 'lira_validation_state')
    def _compute_lira_waiting_minutes(self):
        now = datetime.now()
        for wo in self:
            if wo.lira_validation_state == 'pending' and wo.lira_date_ready:
                delta = now - wo.lira_date_ready.replace(tzinfo=None)
                wo.lira_waiting_minutes = math.floor(delta.total_seconds() / 60)
            else:
                wo.lira_waiting_minutes = 0

    def write(self, vals):
        qty_before = {}
        if 'qty_ready_to_validate' in vals:
            qty_before = {wo.id: wo.qty_ready_to_validate for wo in self}
        result = super().write(vals)
        if qty_before:
            new_qty = vals.get('qty_ready_to_validate', 0)
            for wo in self:
                if qty_before.get(wo.id, 0) == 0 and new_qty > 0:
                    wo.lira_date_ready = fields.Datetime.now()
                    names = ', '.join(wo.employee_ids.mapped('name'))
                    wo.lira_requested_by_names = names or wo.texto_fichados or ''
                elif new_qty == 0:
                    wo.lira_date_ready = False
        return result

    def action_open_production(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'res_id': self.production_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_open_validate_wizard(self):
        return {
            'name': 'Validar cantidad',
            'type': 'ir.actions.act_window',
            'res_model': 'lira.validate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_qty_to_validate': self.qty_ready_to_validate,
                'default_qty_pending': self.qty_ready_to_validate,
                'default_wizard_mode': 'validate',
            },
        }

    def action_open_reject_wizard(self):
        return {
            'name': 'Rechazar cantidad',
            'type': 'ir.actions.act_window',
            'res_model': 'lira.validate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_qty_to_validate': self.qty_ready_to_validate,
                'default_qty_pending': self.qty_ready_to_validate,
                'default_wizard_mode': 'reject',
            },
        }
