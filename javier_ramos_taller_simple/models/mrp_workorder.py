# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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
class MrpWorkorder(models.Model):
    _inherit = ['mrp.workorder']
    validado = fields.Boolean(
        string="Validado", copy=False
    )

    def button_start(self, raise_on_invalid_state=False, bypass=False):
        _logger.info('----------------- button_start -----------')
        skip_employee_check = bypass or (not request and not self.env.user.employee_id)
        main_employee = False
        if not skip_employee_check:
            if not self.env.context.get('mrp_display'):
                main_employee = self.env.user.employee_id.id
                if not self.env.user.employee_id:
                    raise UserError(_("You need to link this user to an employee of this company to process the work order"))
            else:
                connected_employees = self.env['hr.employee'].get_employees_connected()
                if len(connected_employees) == 0:
                    raise UserError(_("You need to log in to process this work order."))
                main_employee = self.env['hr.employee'].get_session_owner()
                if not main_employee:
                    raise UserError(_("There is no session chief. Please log in."))
            if any(main_employee not in [emp.id for emp in wo.allowed_employees] and not wo.all_employees_allowed for wo in self):
                raise UserError(_("You are not allowed to work on the workorder"))
            
        if any(wo.working_state == 'blocked' for wo in self):
            raise UserError(_('Please unblock the work center to start the work order.'))
        for wo in self:
            if any(not time.date_end for time in wo.time_ids.filtered(lambda t: t.user_id.id == self.env.user.id)):
                continue
            if wo.state in ('done', 'cancel'):
                if raise_on_invalid_state:
                    continue
                raise UserError(_('You cannot start a work order that is already done or cancelled'))


            if wo._should_start_timer():
                self.env['mrp.workcenter.productivity'].create(
                    wo._prepare_timeline_vals(wo.duration, fields.Datetime.now())
                )

            if wo.production_id.state != 'progress':
                wo.production_id.write({
                    'date_start': fields.Datetime.now()
                })
            if wo.state == 'progress':
                continue
            date_start = fields.Datetime.now()
            vals = {
                'state': 'progress',
                'date_start': date_start,
            }
            if not wo.leave_id:
                leave = self.env['resource.calendar.leaves'].create({
                    'name': wo.display_name,
                    'calendar_id': wo.workcenter_id.resource_calendar_id.id,
                    'date_from': date_start,
                    'date_to': date_start + relativedelta(minutes=wo.duration_expected),
                    'resource_id': wo.workcenter_id.resource_id.id,
                    'time_type': 'other'
                })
                vals['date_finished'] = leave.date_to
                vals['leave_id'] = leave.id
                wo.write(vals)
            else:
                if not wo.date_start or wo.date_start > date_start:
                    vals['date_start'] = date_start
                    vals['date_finished'] = wo._calculate_date_finished(date_start)
                if wo.date_finished and wo.date_finished < date_start:
                    vals['date_finished'] = date_start
                wo.with_context(bypass_duration_calculation=True).write(vals)
        #Iniciar/Finalizar Asistencia
        trajabador_id = self.env['hr.employee'].search([('id', '=',main_employee)], limit = 1)
        if trajabador_id and trajabador_id.attendance_state == 'checked_out':
            self.env['hr.attendance'].iniciar_finalizar_empleado(trabajador_id=trajabador_id)


        for wo in self:
            if len(wo.time_ids) == 1 or all(wo.time_ids.mapped('date_end')):
                for check in wo.check_ids:
                    if check.component_id:
                        check._update_component_quantity()

            if main_employee:
                if (len(wo.allowed_employees) == 0 or main_employee in [emp.id for emp in wo.allowed_employees]) and wo.state not in ('done', 'cancel'):
                    wo.start_employee(self.env['hr.employee'].browse(main_employee).id)
                    wo.employee_ids |= self.env['hr.employee'].browse(main_employee)

   
    
