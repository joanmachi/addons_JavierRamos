
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


class TipoPalet(models.Model):
    _name = 'plastec_taller.tipo_palet'

    name = fields.Char(string='Nombre')
    cantidad_cajas = fields.Integer(string='Cantidad de cajas')
