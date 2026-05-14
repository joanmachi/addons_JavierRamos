
from ast import literal_eval
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from pytz import utc

from odoo import Command, api, fields, models, _
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
from odoo.addons.resource.models.utils import Intervals, sum_intervals
from odoo.http import request

import logging


_logger = logging.getLogger(__name__)
class HrAttendance(models.Model):
    _inherit = ['hr.attendance']

  
    def iniciar_taller_pin(self, pin = False):
        _logger.info('-------------------------------')
        _logger.info(pin)
        _logger.info('-------------------------------')
        if not pin:
            raise ValidationError('Tiene que introducir un PIN')
        trabajador_id = self.env['hr.employee'].search([('pin', '=', pin)], limit = 1)
        if not trabajador_id:
            raise ValidationError('No se encontro a un empleado con ese PIN')
        return self.iniciar_finalizar_empleado(trabajador_id=trabajador_id)
        
    def iniciar_finalizar_empleado(self, trabajador_id):
        if trabajador_id and trabajador_id.attendance_state == 'checked_in':
            _logger.info('trabajador_id and trabajador_id.attendance_state ==  checked_in')
            productivity = self.env['mrp.workcenter.productivity'].search([('date_end', '=', False), ('employee_id', '=', trabajador_id.id)])
            _logger.info(len(productivity))
            contador = 0
            msg_ordenes = 'Hay ordenes en marcha: \n'
            for line in productivity:
                contador = contador + 1
                msg_ordenes = msg_ordenes + ('%s - %s \n' % (line.production_id.name, line.workorder_id.name))
            if contador > 0:
                raise ValidationError(msg_ordenes)
        trabajador_id._attendance_action_change()
        msg = ''
        if trabajador_id.attendance_state == 'checked_in':
            msg = 'Iniciado asistencia de %s' % (trabajador_id.name)
        else:
            msg = 'Terminado asistencia de %s' % (trabajador_id.name)
        return {'msg' : msg}
