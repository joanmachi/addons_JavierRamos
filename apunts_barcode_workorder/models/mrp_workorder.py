from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.addons.resource.models.utils import Intervals, sum_intervals
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, format_datetime, float_is_zero, float_round
from odoo.http import request

import logging


_logger = logging.getLogger(__name__)


# Importamos la clave de contexto del otro modulo para mantenerlo en un solo sitio.
from .mrp_production import APUNTS_AUTO_BACKORDER_CTX


class WorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    qty_ready_to_validate = fields.Float(string="Cant. por validar", default=0.0, copy=False)
    qty_validated = fields.Float(string="Cant. validada", default=0.0, copy=False)
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
        for wo in self:
            wo.texto_fichados = ', '.join(wo.employee_ids.mapped('name'))

    @api.depends('production_id.workorder_ids.qty_validated')
    def _compute_prev_validated_qty(self):
        for wo in self:
            all_wos = wo.production_id.workorder_ids.sorted('sequence')
            prev_wos = all_wos.filtered(lambda w: w.sequence < wo.sequence)
            es_conjunto = wo.production_id.product_id.product_tmpl_id.tipo_producto == 'conjunto'

            if es_conjunto or not prev_wos:
                wo.prev_validated_qty = wo.production_id.product_qty - wo.qty_validated
            else:
                wo.prev_validated_qty = prev_wos[-1].qty_validated - wo.qty_validated

  
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

    # ------------------------------------------------------------------
    # Auto-producir + auto-back-order: trigger en write de qty_validated
    # (apunts_barcode_workorder >= 18.0.1.0.4)
    # ------------------------------------------------------------------

    def write(self, vals):
        """Override para disparar `_apunts_auto_producir_y_backorder` cuando
        se incrementa `qty_validated` en la ULTIMA fase de una produccion.

        Casos en los que NO disparamos:
        - El contexto trae la flag `apunts_skip_auto_backorder` (reentrancia).
        - El write no toca `qty_validated`.
        - La WO no es la ultima fase de su produccion.
        - La produccion no esta en estado "abierto" (confirmed/progress/to_close).
        - Tras el write, qty_validated == 0 (no se ha avanzado nada).
        """
        # Si no se toca qty_validated o estamos en el propio flujo, atajo.
        if 'qty_validated' not in vals or self.env.context.get(APUNTS_AUTO_BACKORDER_CTX):
            return super().write(vals)

        # Tomar snapshot de cambios antes para saber a quien disparar.
        wos_a_evaluar = []
        for wo in self:
            qty_prev = wo.qty_validated or 0.0
            qty_new = vals.get('qty_validated', qty_prev)
            if float_compare(qty_new, qty_prev, precision_digits=6) > 0:
                wos_a_evaluar.append(wo.id)

        res = super().write(vals)

        if not wos_a_evaluar:
            return res

        # Tras el write, disparar el auto-flujo en aquellas WOs que sean
        # ultima fase y cuya produccion siga abierta.
        for wo in self.browse(wos_a_evaluar):
            try:
                production = wo.production_id
                if not production or production.state not in ('confirmed', 'progress', 'to_close'):
                    continue
                if not production._apunts_es_ultima_fase(wo):
                    continue
                if float_is_zero(wo.qty_validated or 0.0, precision_digits=6):
                    continue
                _logger.info(
                    "[apunts_auto_backorder] Trigger desde WO %s (%s), prod %s, qty_validated=%s",
                    wo.id, wo.name, production.name, wo.qty_validated,
                )
                production._apunts_auto_producir_y_backorder(wo.qty_validated)
            except UserError:
                # Propaga al usuario, ya logueado en _apunts_auto_producir_y_backorder
                raise
            except Exception:
                _logger.exception(
                    "[apunts_auto_backorder] Fallo no controlado en trigger WO %s",
                    wo.id,
                )
                raise

        return res
