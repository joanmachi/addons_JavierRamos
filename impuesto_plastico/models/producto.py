# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from itertools import product
import math
from odoo import models, fields, api
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
import logging


_logger = logging.getLogger(__name__)


class Producto(models.Model):
    _inherit = "product.template"

    exento_impuesto = fields.Boolean("Exento de impuesto")


