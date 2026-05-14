from odoo import api, fields, models, _

import logging


_logger = logging.getLogger(__name__)
class ManufacturingOrder(models.Model):
    _inherit = 'mrp.production'


    def comprobar_disponibilidad(self):

        self.action_assign()
        if self.reservation_state != 'assigned' and self.components_availability_state in ('late', 'unavailable', 'expected'):
            return {
                'error': True,
                'mensaje': 'No hay componentes'
            }
        if self.reservation_state == 'assigned':
            return {
                'error': False,
                'mensaje': 'Componentes asignados'
            }
    def iniciar_parar_orden(self, barcode, empleado):
        orden = self.env['mrp.workorder'].search([('barcode', '=', barcode)], limit = 1)
        for orden in self.workorder_ids:
 
            if orden.production_id.reservation_state != 'assigned' and orden.production_id.components_availability_state in ('late', 'unavailable', 'expected'):
                return {
                    'error': True,
                    'mensaje': 'No hay componentes'
                }
            if orden.barcode == barcode:
                if orden.prev_validated_qty == 0:
                    return {
                        'error': True,
                        'mensaje': 'La orden no tiene cantidad a producir'
                    }
                orden_iniciada = False
               
                if empleado['id'] in orden.employee_ids.ids:
                    orden_iniciada = True

                if not orden_iniciada:
                    orden.start_employee(employee_id = empleado['id'])
                    return {
                        'error': False,
                        'mensaje': 'Iniciado correctamente'
                    }
                else:
                    orden.stop_employee([empleado['id']])
                    return {
                        'error': False,
                        'mensaje': 'Finalizado correctamente'
                    }

        return {
            'error': True,
            'mensaje': 'No se pudo iniciar la orden'
        }

    def _get_stock_barcode_data(self):
        data = super()._get_stock_barcode_data()
        ordenes = self.workorder_ids.sorted('sequence')

        data['log_note'] = self.log_note
        data['workorders'] = ordenes.read(ordenes._get_fields_stock_barcode(), load=False)
        data['product_image'] = self.product_id.image_256
        data['qty_produced'] = int(round(self.qty_produced or 0))
        data['product_qty'] = int(round(self.product_qty or 0))
        data['product_uom_name'] = self.product_uom_id.name or ''
        for wo_data in data['workorders']:
            wo_record = self.env['mrp.workorder'].browse(wo_data['id'])
            wo_data['prev_validated_qty'] = wo_record.prev_validated_qty
            mins = int(round(wo_record.duration_expected or 0))
            if mins >= 60:
                h, m = divmod(mins, 60)
                wo_data['duration_str'] = f"{h}h {m:02d}m" if m else f"{h}h"
            elif mins > 0:
                wo_data['duration_str'] = f"{mins}m"
            else:
                wo_data['duration_str'] = ''
        _logger.info('data')
        _logger.info(data)
        return data

    def enviar_notificacion(self, cantidad, trabajador, nombre_orden):
        _logger.info('------- enviar_notificacion')
        _logger.info(cantidad)
        _logger.info(trabajador)
        if self.user_id:
            """
            self.message_post(
                body=f"El {trabajador['name']} a cambiado la cantidad a validar. Nueva cantidad: {cantidad}",
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[self.user_id.partner_id.id]
                )
            """
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary="Orden de trabajo actualizada",
                note=f"El operario {trabajador['name']} a actualizado la cantidad de la orden {nombre_orden}({self.name}). Nueva cantidad: {cantidad}."
            )
    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + ['log_note']

    def get_componentes_barcode(self):
        componentes = []
        for move in self.move_raw_ids.filtered(lambda m: m.state != 'cancel'):
            componentes.append({
                'id':           move.id,
                'nombre':       move.product_id.display_name,
                'referencia':   move.product_id.default_code or '',
                'cantidad':     move.product_uom_qty,
                'hecho':        move.quantity,
                'uom':          move.product_uom.name,
                'estado':       move.state,
            })
        return componentes