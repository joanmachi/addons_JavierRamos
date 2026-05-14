# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class Usuario(models.Model):
    _inherit = 'res.users'

    @api.model
    def _get_fields_stock_barcode(self):
        return [
            'id',
            'name'
        ]
