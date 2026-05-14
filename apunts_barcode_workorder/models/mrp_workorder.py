from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.addons.resource.models.utils import Intervals, sum_intervals
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, format_datetime, float_is_zero, float_round
from odoo.http import request

import logging


_logger = logging.getLogger(__name__)
class WorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    qty_ready_to_validate = fields.Float(string="Cant. por validar", default=0.0)
    qty_validated = fields.Float(string="Cant. validada", default=0.0)
    prev_validated_qty = fields.Float(
        string="Qty from Previous Stage", 
        compute="_compute_prev_validated_qty"
    )
    
    texto_fichados = fields.Char(
        string="Fichados", 
        compute="_compute_texto_fichados"
    )
    

    @api.depends('employee_ids')
    def _compute_texto_fichados(self):
        _logger.info('_compute_texto_fichados')
        for wo in self:
            texto_fichados = ''
            fichajes = []
            for fichada in wo.employee_ids:
                fichajes.append(fichada.name)
            texto_fichados = ', '.join(fichajes)
            wo.texto_fichados = texto_fichados
    @api.depends('production_id.workorder_ids.qty_validated')
    def _compute_prev_validated_qty(self):
        _logger.info('_compute_prev_validated_qty')
        for wo in self:
            # Sort all workorders of this MO by sequence
            all_wos = wo.production_id.workorder_ids.sorted('sequence')
            # Find workorders with a lower sequence
            prev_wos = all_wos.filtered(lambda w: w.sequence < wo.sequence)
            
            if prev_wos:
                # Get the validated qty of the immediate predecessor
                wo.prev_validated_qty = prev_wos[-1].qty_validated - wo.qty_validated

            else:
                # First workorder: Limit is the total MO quantity
                wo.prev_validated_qty = wo.production_id.product_qty - wo.qty_validated

  
    def finalizar_fichaje(self,empleado, qty=0):
        if empleado and empleado['id']:
            for orden in self:
                #if (orden.qty_ready_to_validate) >= orden.prev_validated_qty:
                for empleado_id in orden.employee_ids:
                    if empleado['id'] == empleado_id.id:
                        if qty > 0:
                            for fichaje in orden.time_ids:
                                if fichaje.employee_id.id == empleado_id.id and (not fichaje.date_end):
                                    fichaje.write({
                                        'cantidad_introducida' : qty,
                                        'cantidad_total_actual' : orden.qty_ready_to_validate
                                    })
                                    break 
                        orden.stop_employee([empleado['id']])
    def action_open_qty_wizard(self):
        return {
            'name': 'Validar cantidades',
            'type': 'ir.actions.act_window',
            'res_model': 'workorder.qty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_new_qty': 0
            }
        }
    





    def _get_fields_stock_barcode(self):
        return [
            'id',
            'name',
            'barcode',
            'duration',
            'employee_id',
            'employee_ids',
            'employee_name',
            'working_user_ids',
            'qty_done',
            'qty_produced',
            'qty_producing',
            'qty_remaining',
            'qty_ready_to_validate',
            'qty_validated',
            'prev_validated_qty',
            'texto_fichados',
        ]
    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        for wo_data in res.get('workorders', []):
            wo = self.browse(wo_data['id'])
            wo_data['prev_validated_qty'] = wo.prev_validated_qty
            wo_data['texto_fichados'] = wo.texto_fichados
        return res
 