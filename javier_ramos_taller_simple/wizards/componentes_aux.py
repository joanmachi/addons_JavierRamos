# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class ComponenteAux(models.TransientModel):
    _name = "javier_ramos_taller_simple.componentes_aux"

    producto = fields.Many2one(
        'product.template',
        string='Producto',
        required = True,
    )
 


               
        

    precio_unidad = fields.Float(
        string="Precio(Kg)", store=True
    )
    cantidad = fields.Float(string="Cantidad(Kg)",default=1)
    tiempo_recepcion = fields.Float(string="Tiempo recepción",default=7)
    total = fields.Float(string="total")

    cuestionario_aux = fields.Many2one(
        'javier_ramos_taller_simple.cuestionario',
        string='Cuestionario'
    )

    @api.onchange("producto", "cantidad")
    def onchange_producto(self):
        self.precio_unidad =  self.producto.standard_price
        self.total = self.cantidad * self.precio_unidad
  