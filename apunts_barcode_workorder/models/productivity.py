from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.addons.resource.models.utils import Intervals, sum_intervals
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, format_datetime, float_is_zero, float_round
from odoo.http import request

import logging


_logger = logging.getLogger(__name__)
class Productivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    cantidad_introducida = fields.Float(string="Cantidad", default=0.0)
    cantidad_total_actual = fields.Float(string="Cantidad total", default=0.0)
   