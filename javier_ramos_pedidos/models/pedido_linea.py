# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
import math
import logging


_logger = logging.getLogger(__name__)
class PedidoLinea(models.Model):
    _inherit = "sale.order.line"

    pos_palet =fields.Text(string='POS.')

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super(PedidoLinea, self)._prepare_invoice_line(
            **optional_values)
        res.update({
            "pos_palet": self.pos_palet,
        })
        return res

