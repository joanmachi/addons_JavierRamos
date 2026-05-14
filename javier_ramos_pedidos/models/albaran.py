from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
import json
import logging
from datetime import date, timedelta
from odoo.tools import format_date

_logger = logging.getLogger(__name__)
class Albaran(models.Model):
    _inherit = "stock.picking"


    def _set_sale_id(self):
        res = super(Albaran,self)._set_sale_id()
        if self.sale_id and self.sale_id.commitment_date:
            self.scheduled_date = self.sale_id.commitment_date



    total_value = fields.Monetary(string="Total Value", compute="_compute_total_value", store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.depends('move_ids.product_id', 'move_ids.product_uom_qty', 'sale_id', 'purchase_id')
    def _compute_total_value(self):
        for picking in self:
            value = 0
            for move in picking.move_ids:
                # 1. Sales Pickings: Use Unit Price from Sale Order Line
                if picking.sale_id and move.sale_line_id:
                    value += move.sale_line_id.price_unit * move.product_uom_qty
                
                # 2. Purchase Pickings: Use Unit Price from Purchase Order Line
                elif picking.purchase_id and move.purchase_line_id:
                    value += move.purchase_line_id.price_unit * move.product_uom_qty
                
                # 3. MRP / Internal / Others: Use Product Standard Price (Cost)
                else:
                    value += move.product_id.standard_price * move.product_uom_qty
            
            picking.total_value = value



class AlbaranLinea(models.Model):
    _inherit = "stock.move"

    pos_palet =fields.Text(string='POS.', related="sale_line_id.pos_palet", readonly=True)



class AlbaranMoveLinea(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_properties(self, move_line=False, move=False):
        res = super(AlbaranMoveLinea,
                    self)._get_aggregated_properties(move_line=move_line, move=move)
        if move_line:
            res.update({
                "pos_palet": move_line.move_id.pos_palet,
            })
        return res

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def get_label_key(d_str):
            if not d_str: return ""
            d = fields.Date.from_string(d_str)
            today = date.today()
            if d == today: return _("Today")
            if d == today + timedelta(days=1): return _("Tomorrow")
            if d == today - timedelta(days=1): return _("Yesterday")
            return d.strftime('%d %b') # Standard Odoo fallback format

    def _compute_kanban_dashboard_graph(self):
 
        super()._compute_kanban_dashboard_graph()
        lang = self.env.user.lang or 'es_ES'
        self_lang = self.with_context(lang=lang)
        def parse_odoo_date(date_str):
            """Parses '24 feb 2026' into a date object"""
            if not date_str or not isinstance(date_str, str):
                return date_str
            
            # Spanish month map (common Odoo abbreviations)
            months = {
                'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12
            }
            parts = date_str.lower().replace('.', '').split()
            if len(parts) == 3:
                try:
                    day = int(parts[0])
                    month = months.get(parts[1])
                    year = int(parts[2])
                    if month:
                        return date(year, month, day)
                except (ValueError, TypeError):
                    pass
            return None
        
        for record in self:
            if not record.kanban_dashboard_graph:
                continue
                
            graph_data = json.loads(record.kanban_dashboard_graph)
            is_mrp = record.code == 'mrp_operation'
            model_name = 'mrp.production' if is_mrp else 'stock.picking'
            date_field = 'date_start' if is_mrp else 'scheduled_date'
            
            groups = self.env[model_name].read_group(
                domain=[('picking_type_id', '=', record.id), ('state', 'not in', ['done','cancel', 'draft'])],
                fields=['total_value'],
                groupby=[f'{date_field}:day'],
                lazy=False
            )

         
            today = date.today()
            value_map = {}

          

            for g in groups:
                raw_date = g.get(f'{date_field}:day')
                
                d = parse_odoo_date(raw_date)
                if d is None:
                    continue
                if d < today - timedelta(days=1):
                    label = "Antes"
                elif d == today - timedelta(days=1): 
                    label = "Ayer"
                elif d == today: 
                    label = "Hoy"
                elif d == today + timedelta(days=1): 
                    label = "Mañana"
                elif d == today + timedelta(days=2): 
                    label = "Pasado mañana"
                elif d > today + timedelta(days=2): 
                    label = "Después de"
                else: 
                    label = d.strftime('%d %b').lower()
                
                value_map[label] = value_map.get(label, 0.0) + g.get('total_value', 0.0)
       

                

            for entry in graph_data[0]['values']:
                label = entry.get('label')
                entry['total_amount'] = value_map.get(label, 0.0)

       
            record.kanban_dashboard_graph = json.dumps(graph_data)
  