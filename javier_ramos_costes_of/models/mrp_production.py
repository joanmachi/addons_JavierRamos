from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    jr_is_parcial = fields.Boolean(
        string='Es parcial',
        compute='_compute_jr_cadena_info',
    )
    jr_cadena_count = fields.Integer(
        string='OFs en cadena',
        compute='_compute_jr_cadena_info',
    )

    @api.depends('procurement_group_id', 'name')
    def _compute_jr_cadena_info(self):
        for prod in self:
            cadena = prod._apunts_get_cadena()
            prod.jr_cadena_count = len(cadena)
            prod.jr_is_parcial = len(cadena) > 1

    def action_jr_costes_cadena(self):
        self.ensure_one()
        cadena = self._apunts_get_cadena()
        raiz = cadena.sorted('id')[0].name if cadena else self.name

        list_view = self.env.ref(
            'apunts_jr_wip_costes_of.apunts_view_mrp_production_wip_list',
            raise_if_not_found=False,
        )
        search_view = self.env.ref(
            'apunts_jr_wip_costes_of.apunts_view_mrp_production_wip_search',
            raise_if_not_found=False,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': f'Costes cadena — {raiz}',
            'res_model': 'mrp.production',
            'view_mode': 'list',
            'views': [(list_view.id if list_view else False, 'list')],
            'search_view_id': search_view.id if search_view else False,
            'domain': [('id', 'in', cadena.ids)],
            'target': 'current',
        }
