from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LiraValidateWizard(models.TransientModel):
    _name = 'lira.validate.wizard'
    _description = 'Wizard validación/rechazo supervisor'

    workorder_id    = fields.Many2one('mrp.workorder', required=True, readonly=True)
    production_name = fields.Char(related='workorder_id.lira_production_seq', readonly=True)
    product_name    = fields.Char(related='workorder_id.production_id.product_id.display_name', readonly=True)
    workorder_name  = fields.Char(related='workorder_id.name', readonly=True)
    operator_names  = fields.Char(related='workorder_id.texto_fichados', readonly=True)

    # Float normal con default desde contexto — evita el problema de related en TransientModel
    qty_pending     = fields.Float(string='Solicitado por operario', readonly=True, digits=(16, 2))
    qty_to_validate = fields.Float(string='Cantidad a validar', digits=(16, 2))

    wizard_mode     = fields.Selection([
        ('validate', 'Validar'),
        ('reject',   'Rechazar'),
    ], default='validate', required=True)
    rejection_note  = fields.Char(string='Motivo del rechazo')

    def action_validate(self):
        self.ensure_one()
        wo = self.workorder_id
        qty = self.qty_to_validate

        if qty <= 0:
            raise ValidationError("La cantidad a validar debe ser mayor a 0.")
        if qty > wo.qty_ready_to_validate:
            raise ValidationError(
                f"No puedes validar más de {wo.qty_ready_to_validate} unidades (cantidad entregada por el operario)."
            )

        wo.write({
            'qty_validated': wo.qty_validated + qty,
            'qty_ready_to_validate': wo.qty_ready_to_validate - qty,
            'lira_validated_by': self.env.user.id,
            'lira_validated_date': fields.Datetime.now(),
            'lira_supervisor_note': False,
        })

        all_wos = wo.production_id.workorder_ids.sorted('sequence')
        next_wos = all_wos.filtered(lambda w: w.sequence > wo.sequence)
        if not next_wos:
            wo.production_id.write({'qty_producing': wo.production_id.qty_producing + qty})

        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'mrp.production'),
            ('res_id', '=', wo.production_id.id),
            ('summary', '=', 'Orden de trabajo actualizada'),
        ])
        if activities:
            activities.action_feedback(
                feedback=f"Validado {qty} uds. en '{wo.name}' por {self.env.user.name}"
            )

        self.env.user._bus_send("barcode_refresh_requested", {'production_id': wo.production_id.id})
        return {'type': 'ir.actions.act_window_close'}

    def action_reject(self):
        self.ensure_one()
        if not self.rejection_note:
            raise ValidationError("Debes indicar el motivo del rechazo.")

        wo = self.workorder_id
        wo.write({
            'qty_ready_to_validate': 0,
            'lira_date_ready': False,
            'lira_supervisor_note': self.rejection_note,
            'lira_rejection_date': fields.Datetime.now(),
        })

        self.env.user._bus_send("barcode_refresh_requested", {'production_id': wo.production_id.id})
        return {'type': 'ir.actions.act_window_close'}
