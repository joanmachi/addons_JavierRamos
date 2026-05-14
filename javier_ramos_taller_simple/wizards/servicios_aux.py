# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class ServiciosAux(models.TransientModel):
    _name = "javier_ramos_taller_simple.servicios_aux"

    producto = fields.Many2one(
        'product.template',
        string='Servicio',
        required = True,
        domain = [('categ_id.name', '=', 'SERVICIOS SUBCONTRATADOS')]
    )
    
        
 
    precio_unidad = fields.Float(
        string="Precio(m²)", related="producto.standard_price", readonly=True, store=True
    )
    cantidad = fields.Float(string="Cantidad(m²)",default=1)
    total = fields.Float(string="total")
    tiempo_esperado = fields.Float(string="Tiempo esperado",default=5)

    cuestionario_aux = fields.Many2one(
        'javier_ramos_taller_simple.cuestionario',
        string='Cuestionario'
    )

    tipo_producto = fields.Selection(related='cuestionario_aux.tipo_producto',
        selection= [('unitario', 'Unitario'),('serie', 'Serie'),('conjunto', 'Conjunto')]
    )


    @api.onchange("producto", "cantidad")
    def onchange_producto(self):
        self.total = self.cantidad * self.producto.standard_price
  