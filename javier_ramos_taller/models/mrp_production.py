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
class MrpProduction(models.Model):
    _inherit = ['mrp.production']

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Reference must be unique per Company!'),
        ('qty_positive', 'check (1=1)', 'The quantity to produce must be positive!'),
    ]
  
    def add_cantidad(self, cantidad = 0, order_id = False):
        _logger.info('add_cantidad')
        workorder_id = False
        if order_id:
            _logger.info('if order_id:')
            workorder_id = self.env['mrp.workorder'].search([('id', '=', order_id)], limit = 1)[0]
        if workorder_id and not workorder_id.is_last_unfinished_wo:
           
            _logger.info('if workorder_id and not workorder_id.is_last_unfinished_wo:')
            _logger.info(workorder_id.qty_produced)
            _logger.info(cantidad)
            _logger.info(workorder_id.qty_produced + float(cantidad))
            workorder_id.write({'qty_produced' : (workorder_id.qty_produced + float(cantidad))})
        else:
            _logger.info('else:')
            self.qty_producing = self.qty_producing + float(cantidad)
        

    def _set_quantities(self):
        self.ensure_one()
        missing_lot_id_products = ""
        if self.product_tracking in ('lot', 'serial') and not self.lot_producing_id:
            self.action_generate_serial()
        if self.product_tracking == 'serial' and float_compare(self.qty_producing, 1, precision_rounding=self.product_uom_id.rounding) == 1:
            self.qty_producing = 1
     
        self._set_qty_producing()

        for move in self.move_raw_ids:
            if move.state in ('done', 'cancel') or not move.product_uom_qty:
                continue
            rounding = move.product_uom.rounding
            if move.manual_consumption:
                if move.has_tracking in ('serial', 'lot') and (not move.picked or any(not line.lot_id for line in move.move_line_ids if line.quantity and line.picked)):
                    missing_lot_id_products += "\n  - %s" % move.product_id.display_name
        if missing_lot_id_products:
            error_msg = _(
                "You need to supply Lot/Serial Number for products and 'consume' them: %(missing_products)s",
                missing_products=missing_lot_id_products,
            )
            raise UserError(error_msg)