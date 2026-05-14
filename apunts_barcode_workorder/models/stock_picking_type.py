from odoo import fields, models

import logging


_logger = logging.getLogger(__name__)
class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def get_action_picking_tree_ready_kanban(self):
        _logger.info('----------- get_action_picking_tree_ready_kanban')
        res = super().get_action_picking_tree_ready_kanban()
        _logger.info('----------- res')
        _logger.info(res)
        
        workcenter = False
        filtro = ""
        if self.sequence_code and self.sequence_code == 'S01':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_7'

        if self.sequence_code and self.sequence_code == 'S02':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_8'
            

        if self.sequence_code and self.sequence_code == 'S03':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_9'
            

        if self.sequence_code and self.sequence_code == 'C01':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_10'
            

        if self.sequence_code and self.sequence_code == 'C02':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_11'
            

        if self.sequence_code and self.sequence_code == 'C04':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_12'
            

        if self.sequence_code and self.sequence_code == 'C05':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_13'
            

        if self.sequence_code and self.sequence_code == 'T01':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_14'
            

        if self.sequence_code and self.sequence_code == 'T02':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_15'
            

        if self.sequence_code and self.sequence_code == 'T03':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_16'
            

        if self.sequence_code and self.sequence_code == 'T04':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_17'
            

        if self.sequence_code and self.sequence_code == 'T05':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_18'
            

        if self.sequence_code and self.sequence_code == 'F01':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_19'
            

        if self.sequence_code and self.sequence_code == 'F02':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_20'
            

        if self.sequence_code and self.sequence_code == 'L01':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_21'
            

        if self.sequence_code and self.sequence_code == 'M01':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_22'
            

        if self.sequence_code and self.sequence_code == 'TRABAJOS_MANUALES':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_32'
            

        if self.sequence_code and self.sequence_code == 'SERVICIOS_EXTERNOS':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_36'
            

        if self.sequence_code and self.sequence_code == 'PROGRAMACION':
            workcenter = self.env['mrp.workcenter'].search([('code', '=', self.sequence_code)], limit=1)
            filtro = 'search_default_filter_by_workcenter_38'
            

            
        if workcenter:
            
            res['context'].update({
                filtro : 1,
                'search_default_picking_type_id': 11,
            })
                        
             
        return res
    
