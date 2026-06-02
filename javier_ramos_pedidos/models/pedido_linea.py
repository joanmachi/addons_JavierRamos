# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
import math
import logging


_logger = logging.getLogger(__name__)
class PedidoLinea(models.Model):
    _inherit = "sale.order.line"

    pos_palet = fields.Text(string='POS.')

    # Reusamos el compute de sale_stock (que también asigna display_qty_widget).
    # store=True es necesario para poder usar el campo en filtros de búsqueda.
    qty_to_deliver = fields.Float(
        string='Pdte. entrega',
        compute='_compute_qty_to_deliver',
        store=True,
        digits='Product Unit of Measure',
    )

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super(PedidoLinea, self)._prepare_invoice_line(
            **optional_values)
        res.update({
            "pos_palet": self.pos_palet,
        })
        return res

