# -*- coding: utf-8 -*-
"""Ventas por semana: la gráfica del ranking.

Cada vez que se calcula el ranking de ventas/facturación, se guarda también el
total de cada semana (facturado o pedido, según la fuente elegida), para verlo
en una gráfica con las semanas en horizontal y los euros en vertical.
"""
from odoo import api, fields, models


class LiraVentasSemana(models.Model):
    _name = 'lira.ventas.semana'
    _description = 'Ventas por semana (gráfica del ranking)'
    _order = 'semana'

    user_id     = fields.Many2one('res.users', ondelete='cascade', index=True)
    semana      = fields.Date(string='Semana (lunes)', index=True)
    num_semana  = fields.Integer(string='Nº semana')
    anio        = fields.Integer(string='Año')
    importe     = fields.Float(string='Importe (€ s/IVA)', digits=(16, 2))
    qty         = fields.Float(string='Unidades', digits=(16, 2))
    num_docs    = fields.Integer(string='Documentos')
    fuente      = fields.Char(string='Fuente')
    agrupar_por = fields.Char(string='Agrupación')
    date_from   = fields.Date(string='Desde')
    date_to     = fields.Date(string='Hasta')

    @api.model
    def _accion(self, fuente=None, agrupar_por=None):
        """La pantalla de la gráfica (gráfica, tabla dinámica y lista) con las
        semanas que se calcularon junto al último ranking del usuario."""
        graph = self.env.ref('lira_dashboard_contabilidad.view_lira_ventas_semana_graph')
        pivot = self.env.ref('lira_dashboard_contabilidad.view_lira_ventas_semana_pivot')
        lista = self.env.ref('lira_dashboard_contabilidad.view_lira_ventas_semana_list')
        search = self.env.ref('lira_dashboard_contabilidad.view_lira_ventas_semana_search')
        que = 'Facturación' if fuente == 'facturas' else 'Ventas (pedidos confirmados)'
        return {
            'type': 'ir.actions.act_window',
            'name': '%s por semana' % que,
            'res_model': self._name,
            'view_mode': 'graph,pivot,list',
            'views': [(graph.id, 'graph'), (pivot.id, 'pivot'), (lista.id, 'list')],
            'search_view_id': [search.id, 'search'],
            'domain': [('user_id', '=', self.env.user.id)],
            # fill_temporal: las semanas sin ventas salen como barra a cero, no desaparecen
            'context': {'create': False, 'delete': False, 'edit': False, 'fill_temporal': True},
            'target': 'current',
        }
