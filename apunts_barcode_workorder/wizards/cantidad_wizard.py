from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WorkorderQtyWizard(models.TransientModel):
    _name = 'workorder.qty.wizard'
    _description = 'Update Workorder Quantity'

    workorder_id = fields.Many2one('mrp.workorder', string="Workorder", required=True)
    qty_remaining = fields.Float(related='workorder_id.qty_remaining', string="Quantity Remaining")
    new_qty = fields.Float(string="New Quantity", digits='Product Unit of Measure', required=True)

    qty_to_process = fields.Float(related='workorder_id.qty_ready_to_validate', readonly=True)

    def action_confirm(self):
        self.ensure_one()
        # Validation: You might want to ensure they don't validate more than is 'Ready'
        if self.new_qty > self.workorder_id.qty_ready_to_validate:
             raise ValidationError("No puedes validar mas de la cantidad lista.")

        # Update the 'Validated' field
        self.workorder_id.write({
            'qty_validated': self.workorder_id.qty_validated + self.new_qty,
            'qty_ready_to_validate': self.workorder_id.qty_ready_to_validate - self.new_qty,
            'qty_remaining': self.qty_remaining - self.new_qty
        })

        all_wos = self.workorder_id.production_id.workorder_ids.sorted('sequence')
        next_wos = all_wos.filtered(lambda w: w.sequence > self.workorder_id.sequence)
        if not next_wos:
            self.workorder_id.production_id.write({
                'qty_producing' : self.workorder_id.production_id.qty_producing + self.new_qty
            })

    
        self.env.user._bus_send("barcode_refresh_requested", {

                'production_id': self.workorder_id.production_id.id,

            })
        return {'type': 'ir.actions.act_window_close'}
        return {'type': 'ir.actions.client', 'tag': 'reload'}
