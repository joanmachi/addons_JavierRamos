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
class PlPedidoLinea(models.Model):
    _inherit = "sale.order.line"

    cliente_referencia=fields.Text(string='S/Referencia')
    cliente_pedido=fields.Text(string='S/Pedido')

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super(PlPedidoLinea, self)._prepare_invoice_line(
            **optional_values)
        res.update({
            "cliente_referencia": self.cliente_referencia,
            "cliente_pedido": self.cliente_pedido,
        })
        return res


 
