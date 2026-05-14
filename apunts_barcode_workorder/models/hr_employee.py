# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class Empleado(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _get_fields_stock_barcode(self):
        return [
            'id',
            'name'
        ]
    
    def buscar_empleado(self, barcode):
        domain = [['barcode', '=', barcode]]
        fields = ['id', 'name']
        return self.env['hr.employee'].sudo().search_read(domain, fields, load=False)
        
