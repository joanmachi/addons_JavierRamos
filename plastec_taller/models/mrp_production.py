# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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


class MrpProduction(models.Model):
    _inherit = ['mrp.production']


    def action_add_albaran_palet(self):
        self.ensure_one()

        parent_delivery_type = self.env['stock.picking.type'].search([('code', '=', 'internal'), ('name', '=', 'Traslados internos')], limit=1)
        ubicacion_origen = self.env['stock.location'].search([('name', '=', 'Posproducción')], limit=1)
        ubicacion_destino = self.env['stock.location'].search([('name', '=', 'Stock')], limit=1)
        cantidad = 1

        if self.product_id.tipo_palet_id:
            empaquetados = self.env['product.packaging'].search([('product_id', 'in', self.product_id.ids)])
            if len(empaquetados) > 0:
                cantidad = empaquetados[0].qty * self.product_id.tipo_palet_id.cantidad_cajas

        out_picking = self.env['stock.picking'].create({
            'location_id': ubicacion_origen.id,
            'location_dest_id': ubicacion_destino.id,
            'partner_id': False,
            'picking_type_id': parent_delivery_type.id,
            'move_ids': [
                Command.create({
                    'name': self.product_id.name,
                    'location_id': ubicacion_origen.id,
                    'location_dest_id': ubicacion_destino.id,
                    'product_id': self.product_id.id,
                    'product_uom_qty': cantidad,
                    'product_uom': self.product_id.uom_id.id,
                    'description_picking': self.product_id.name,
                })
            ]
        })
        out_picking.button_validate()



        action = self.env['ir.actions.actions']._for_xml_id('mrp_workorder.action_mrp_display')
        action['context'] = {
            'show_all_workorders': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'res_id': out_picking.id,
            'res_model': 'stock.picking',
            'views': [[self.env.ref('plastec_taller.albaran_taller').id, 'form']],
            'name': 'Albaran creado',
            'target': 'new',
            'context': {
            }
        }

    def _get_backorder_mo_vals(self):
        self.ensure_one()
        if not self.procurement_group_id:
            # in the rare case that the procurement group has been removed somehow, create a new one
            self.procurement_group_id = self.env["procurement.group"].create({'name': self.name})
        return {
            'procurement_group_id': self.procurement_group_id.id,
            'move_raw_ids': None,
            'move_finished_ids': None,
            'lot_producing_id': self.lot_producing_id.id,
            'origin': self.origin,
            'state': 'draft' if self.state == 'draft' else 'confirmed',
            'date_deadline': self.date_deadline,
            'orderpoint_id': self.orderpoint_id.id,
        }
  