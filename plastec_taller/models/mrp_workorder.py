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


    def action_add_albaran_palet(self):
        _logger.info('workorder ----- action_add_albaran_palet------')
        self.ensure_one()
        res = self.production_id.action_add_albaran_palet()
        return res