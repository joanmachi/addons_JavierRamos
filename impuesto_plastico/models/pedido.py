# -*- coding: utf-8 -*-

from cgi import test
from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
import logging


_logger = logging.getLogger(__name__)
class Pedido(models.Model):
    _inherit = "sale.order"
    
    

    def _create_invoices(self, grouped=False, final=False, date=None):
        
        _logger.info('*************** impuesto plastico ***************')
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        productoTemplate = self.env['product.product'].search([('name', '=ilike', 'Impuesto especial sobre los envases de plástico no reutilizables')], limit=1).product_tmpl_id
        
        if productoTemplate is None:
            return moves
        
        tax = self.env['account.tax'].search([('name', '=ilike', 'IVA 21% (Bienes)')], limit=1)
        
        total_weight = 0
        
        for factura in moves:
            for line in factura.invoice_line_ids:
                if line.product_id is None:
                    continue
                quantity = line.quantity
                weight = line.product_id.plastic_weight_non_recyclable
                
                if line.product_id.exento_impuesto:
                    self.env['account.move.line'].with_context(
                    check_move_validity=False).create({
                    'move_id': factura.id,
                    'product_id': productoTemplate.id,
                    'quantity': 0,
                    'name': 'Exento del Impuesto al Plástico (Ley 07/22) - '+line.product_id.name,
                    'discount': 0,
                    'price_unit': 0,
                    'account_id': productoTemplate.property_account_income_id.id
                    })
                    continue
                
                if quantity <= 0 or weight <= 0:
                    continue
                total_weight = quantity * weight
                self.env['account.move.line'].with_context(
                    check_move_validity=False).create({
                    'move_id': factura.id,
                    'product_id': productoTemplate.id,
                    'quantity': total_weight,
                    'name': 'Impuesto al Plástico (Ley 07/22) - '+line.product_id.name,
                    'discount': 0,
                    'price_unit': productoTemplate.list_price,
                    'account_id': productoTemplate.property_account_income_id.id,
                    'tax_ids': tax
                })
        
        
            
       
        return moves
