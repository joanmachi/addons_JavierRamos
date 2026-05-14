
import json
import datetime
import math
import re

from ast import literal_eval
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, Command, SUPERUSER_ID
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.tools.misc import OrderedSet, format_date, groupby as tools_groupby, topological_sort


import logging


_logger = logging.getLogger(__name__)
class MrpProduction(models.Model):
    _inherit = ['mrp.production']

    cantidad_caja = fields.Integer("Cajas")
    cantidad_en_caja = fields.Float(string="Cantidad en cajas")


    @api.onchange("product_qty")
    def onchange_cantidad(self):
        if self and self.product_qty > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.cantidad_caja = self.product_uom_qty / multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado
 

    @api.onchange("cantidad_caja")
    def onchange_cantidad_caja(self):
        if self and self.cantidad_caja > 0:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) <= 0:
                return
            multiplo_empaquetado = empaquetados[0].qty
            self.product_qty = self.cantidad_caja * multiplo_empaquetado
            self.cantidad_en_caja = multiplo_empaquetado

  
    def action_confirm(self):
        _logger.info('---------- action_confirm ----------')
        _logger.info('self.picking_ids 1  ')
        _logger.info(self.picking_ids)
        self._check_company()
        moves_ids_to_confirm = set()
        move_raws_ids_to_adjust = set()
        workorder_ids_to_confirm = set()
        for production in self:
            _logger.info('self.picking_ids 2  ')
            _logger.info(self.picking_ids)
            production_vals = {}
            if production.bom_id:
                production_vals.update({'consumption': production.bom_id.consumption})
            # In case of Serial number tracking, force the UoM to the UoM of product
            if production.product_tracking == 'serial' and production.product_uom_id != production.product_id.uom_id:
                production_vals.update({
                    'product_qty': production.product_uom_id._compute_quantity(production.product_qty, production.product_id.uom_id),
                    'product_uom_id': production.product_id.uom_id
                })
                for move_finish in production.move_finished_ids.filtered(lambda m: m.product_id == production.product_id):
                    move_finish.write({
                        'product_uom_qty': move_finish.product_uom._compute_quantity(move_finish.product_uom_qty, move_finish.product_id.uom_id),
                        'product_uom': move_finish.product_id.uom_id
                    })
            if production_vals:
                production.write(production_vals)

            _logger.info('self.picking_ids 3  ')
            _logger.info(self.picking_ids)
            move_raws_ids_to_adjust.update(production.move_raw_ids.ids)
            
            moves_ids_to_confirm.update((production.move_raw_ids | production.move_finished_ids).ids)
            workorder_ids_to_confirm.update(production.workorder_ids.ids)

        move_raws_to_adjust = self.env['stock.move'].browse(sorted(move_raws_ids_to_adjust))
        moves_to_confirm = self.env['stock.move'].browse(sorted(moves_ids_to_confirm))
        workorder_to_confirm = self.env['mrp.workorder'].browse(sorted(workorder_ids_to_confirm))

        move_raws_to_adjust._adjust_procure_method()
       
        moves_to_confirm._action_confirm(merge=False)
        workorder_to_confirm._action_confirm()
        # run scheduler for moves forecasted to not have enough in stock
        ignored_mo_ids = self.env.context.get('ignore_mo_ids', [])
        self.move_raw_ids.with_context(ignore_mo_ids=ignored_mo_ids + self.ids)._trigger_scheduler()
        self.picking_ids.filtered(
            lambda p: p.state not in ['cancel', 'done']).action_confirm()
        # Force confirm state only for draft production not for more advanced state like
        # 'progress' (in case of backorders with some qty_producing)
        self.filtered(lambda mo: mo.state == 'draft').state = 'confirmed'
        _logger.info('self.picking_ids 4')
        _logger.info(self.picking_ids)
        for orden in self:
            for albaran in orden.picking_ids:

                _logger.info(len('for albaran in orden.picking_ids:'))
                _logger.info(len(albaran.move_ids_without_package))
                _logger.info(len(albaran.move_ids))
                for linea in albaran.move_ids_without_package:
                    _logger.info('for linea in res.move_ids_without_package:')
                    empaquetados = self.env['product.packaging'].search([('product_id', 'in', linea.product_id.ids)])
                    if len(empaquetados) <= 0:
                        _logger.info('if len(empaquetados) <= 0:')
                        continue
                    multiplo_empaquetado = empaquetados[0].qty
                    nueva_cantidad = multiplo_empaquetado
                    while True:
                        if nueva_cantidad >= linea.product_uom_qty:
                            break
                        nueva_cantidad = nueva_cantidad + multiplo_empaquetado
                    _logger.info('nueva_cantidad')
                    _logger.info(nueva_cantidad)
                    linea.product_uom_qty = nueva_cantidad
                    linea.quantity = nueva_cantidad
        return True
  