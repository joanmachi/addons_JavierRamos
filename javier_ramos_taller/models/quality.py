# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import float_compare, float_round, is_html_empty



import logging


_logger = logging.getLogger(__name__)
class QualityCheck(models.Model):
    _inherit = "quality.check"

    def update_cantidad_hecha(self, cantidad_hecha):
        self.qty_done = cantidad_hecha
        _logger.info('update_cantidad_hecha')
        _logger.info('self.workorder_id.qty_remaining')
        _logger.info(self.workorder_id.qty_remaining)
        _logger.info('cantidad_hecha')
        _logger.info(cantidad_hecha)
        _logger.info('self.workorder_id.qty_produced + float(cantidad_hecha))')
        _logger.info(self.workorder_id.qty_produced + float(cantidad_hecha))
        _logger.info('self.workorder_id.qty_produced + float(cantidad_hecha)) <= self.workorder_id.qty_remaining')
        _logger.info((self.workorder_id.qty_produced + float(cantidad_hecha)) <= self.workorder_id.qty_remaining)
        if (self.workorder_id.qty_produced + float(cantidad_hecha)) <= self.workorder_id.qty_remaining:
            _logger.info('(if self.workorder_id.qty_produced + float(cantidad_hecha)) <= self.workorder_id.qty_remaining')
            nuevo_check = self.copy(default={'quality_state' : 'none', 'qty_done' : 0, 'previous_check_id': self.id})
            self.workorder_id.current_quality_check_id = nuevo_check