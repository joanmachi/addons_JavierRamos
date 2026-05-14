# -*- coding: utf-8 -*-

from collections import defaultdict, OrderedDict
from datetime import date, datetime, time, timedelta
import json

from odoo import api, fields, models, _
from odoo.tools import float_compare, float_round, format_date, float_is_zero
from odoo.exceptions import UserError

import logging


_logger = logging.getLogger(__name__)
class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'









    @api.model
    def _get_operation_cost(self, operation, workcenter, duration, qty = 0):
        if qty == 0:
            return super()._get_operation_cost(operation, workcenter, duration)
        tiempo_esperado =  (operation.time_cycle * qty) / 60
 
        tiempo_preparacion = workcenter.time_start / 60

        tiempo_limpieza = workcenter.time_stop / 60

        eficencia = workcenter.time_efficiency / 100

        coste_operacion = ((tiempo_esperado/eficencia) + tiempo_preparacion + tiempo_limpieza) * workcenter.costs_hour

      
        return coste_operacion

    @api.model
    def _get_operation_line(self, product, bom, qty, level, index, bom_report_line, simulated_leaves_per_workcenter):
        operations = []
        company = bom.company_id or self.env.company
        operations_planning = {}
        if bom_report_line['availability_state'] in ['unavailable', 'estimated'] and bom.operation_ids:
            qty_to_produce = bom.product_uom_id._compute_quantity(max(0, qty - (product.virtual_available if level > 1 else 0)), bom.product_tmpl_id.uom_id)
            if not float_is_zero(qty_to_produce, precision_rounding=(product or bom.product_tmpl_id).uom_id.rounding):
                max_component_delay = 0
                for component in bom_report_line['components']:
                    line_delay = component.get('availability_delay', 0)
                    max_component_delay = max(max_component_delay, line_delay)
                date_today = self.env.context.get('from_date', fields.date.today()) + timedelta(days=max_component_delay)
                operations_planning = self._simulate_bom_planning(bom, product, datetime.combine(date_today, time.min), qty_to_produce, simulated_leaves_per_workcenter=simulated_leaves_per_workcenter)
                bom_report_line['simulated'] = True
                bom_report_line['max_component_delay'] = max_component_delay
        operation_index = 0
        for operation in bom.operation_ids:
            if not product or operation._skip_operation_line(product):
                continue
            duration_expected = operation._get_duration_expected(product, qty, product.uom_id)
            bom_cost = self.env.company.currency_id.round(self._get_operation_cost(operation, operation.workcenter_id, duration_expected, qty))
            if planning := operations_planning.get(operation, None):
                availability_state = 'estimated'
                availability_delay = (planning['date_finished'].date() - date_today).days
                availability_display = _('Estimated %s', format_date(self.env, planning['date_finished'])) + (" [" + planning['workcenter'].name + "]" if planning['workcenter'] != operation.workcenter_id else "")
            else:
                availability_state = 'available'
                availability_delay = 0
                availability_display = ''
            operations.append({
                'type': 'operation',
                'index': f"{index}{operation_index}",
                'level': level or 0,
                'operation': operation,
                'link_id': operation.id,
                'link_model': 'mrp.routing.workcenter',
                'name': operation.name + ' - ' + operation.workcenter_id.name,
                'uom_name': _("Minutes"),
                'quantity': duration_expected,
                'bom_cost': bom_cost,
                'currency_id': company.currency_id.id,
                'model': 'mrp.routing.workcenter',
                'availability_state': availability_state,
                'availability_delay': availability_delay,
                'availability_display': availability_display,
            })
            operation_index += 1
        return operations
    
    @api.model
    def _get_component_data(self, parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index, product_info, ignore_stock=False):
        _logger.info('------------------ _get_component_data')
        company = parent_bom.company_id or self.env.company
        price = 0
        #variant_seller_ids
        if len(bom_line.product_id.variant_seller_ids) > 0:
            _logger.info('len(bom_line.product_id.variant_seller_ids) > 0')
            for linea_variante in bom_line.product_id.variant_seller_ids:
                _logger.info('for linea_variante in bom_line.product_id.variant_seller_ids:')
                if not linea_variante.product_id or linea_variante.product_id == bom_line.product_id:
                    _logger.info('if linea_variante.product_id is False or linea_variante.product_id == bom_line.product_id:')
                    price = bom_line.product_id.uom_id._compute_price(linea_variante.with_company(company).price, bom_line.product_uom_id) * line_quantity
            _logger.info('linea_variante.product_id')
            _logger.info(linea_variante.product_id)
            _logger.info('linea_variante.product_id == bom_line.product_id')
            _logger.info(linea_variante.product_id )
            _logger.info(bom_line.product_id)
            if price == 0:
                _logger.info('if price == 0:')
                price = bom_line.product_id.uom_id._compute_price(bom_line.product_id.with_company(company).standard_price, bom_line.product_uom_id) * line_quantity
        #seller_ids
        elif len(bom_line.product_id.seller_ids) > 0:
            _logger.info('elif len(bom_line.product_id.seller_ids) > 0:')
   
            price = bom_line.product_id.uom_id._compute_price(bom_line.product_id.seller_ids[0].with_company(company).price, bom_line.product_uom_id) * line_quantity
        else:
            _logger.info('else:')
            price = bom_line.product_id.uom_id._compute_price(bom_line.product_id.with_company(company).standard_price, bom_line.product_uom_id) * line_quantity
        _logger.info('------------------ product_id')
        _logger.info(bom_line.product_id.name)
        _logger.info('------------------ price')
        _logger.info(price)
        _logger.info('------------------ bom_line.product_id.with_company(company).standard_price')
        _logger.info(bom_line.product_id.with_company(company).standard_price)
        
        rounded_price = company.currency_id.round(price)

        key = bom_line.product_id.id
        bom_key = parent_bom.id
        route_info = product_info[key].get(bom_key, {})

        quantities_info = {}
        if not ignore_stock:
            # Useless to compute quantities_info if it's not going to be used later on
            quantities_info = self._get_quantities_info(bom_line.product_id, bom_line.product_uom_id, product_info, parent_bom, parent_product)
        availabilities = self._get_availabilities(bom_line.product_id, line_quantity, product_info, bom_key, quantities_info, level, ignore_stock, bom_line=bom_line)

        has_attachments = False
        if not self.env.context.get('minimized', False):
            has_attachments = self.env['product.document'].search_count(['&', ('attached_on_mrp', '=', 'bom'), '|', '&', ('res_model', '=', 'product.product'), ('res_id', '=', bom_line.product_id.id),
                                                              '&', ('res_model', '=', 'product.template'), ('res_id', '=', bom_line.product_id.product_tmpl_id.id)]) > 0

        return {
            'type': 'component',
            'index': index,
            'bom_id': False,
            'product': bom_line.product_id,
            'product_id': bom_line.product_id.id,
            'product_template_id': bom_line.product_tmpl_id.id,
            'link_id': bom_line.product_id.id if bom_line.product_id.product_variant_count > 1 else bom_line.product_id.product_tmpl_id.id,
            'link_model': 'product.product' if bom_line.product_id.product_variant_count > 1 else 'product.template',
            'name': bom_line.product_id.display_name,
            'code': '',
            'currency': company.currency_id,
            'currency_id': company.currency_id.id,
            'quantity': line_quantity,
            'quantity_available': quantities_info.get('free_qty', 0),
            'quantity_on_hand': quantities_info.get('on_hand_qty', 0),
            'free_to_manufacture_qty': quantities_info.get('free_to_manufacture_qty', 0),
            'base_bom_line_qty': bom_line.product_qty,
            'uom': bom_line.product_uom_id,
            'uom_name': bom_line.product_uom_id.name,
            'prod_cost': rounded_price,
            'bom_cost': rounded_price,
            'route_type': route_info.get('route_type', ''),
            'route_name': route_info.get('route_name', ''),
            'route_detail': route_info.get('route_detail', ''),
            'route_alert': route_info.get('route_alert', False),
            'lead_time': route_info.get('lead_time', False),
            'manufacture_delay': route_info.get('manufacture_delay', False),
            'stock_avail_state': availabilities['stock_avail_state'],
            'resupply_avail_delay': availabilities['resupply_avail_delay'],
            'availability_display': availabilities['availability_display'],
            'availability_state': availabilities['availability_state'],
            'availability_delay': availabilities['availability_delay'],
            'parent_id': parent_bom.id,
            'level': level or 0,
            'has_attachments': has_attachments,
        }






