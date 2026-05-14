# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class Componente(models.TransientModel):
    _name = "javier_ramos_taller_simple.componentes"

    producto = fields.Many2one(
        'product.template',
        string='Producto',
        required = True,
    )




    cantidad = fields.Float(string="Cantidad(Kg)",default=1, digits=(16, 4))
    tiempo_recepcion = fields.Float(string="Tiempo recepción",default=7)
    producto_principal = fields.Many2one(
        'product.template',
        string='Producto'
    )

    precio_unidad = fields.Float(
        string="Precio(Kg)", store=True
    )
    total = fields.Float(string="total")


    @api.onchange("producto_principal")
    def onchange_producto(self):
        for elemento in self:
            elemento.producto = ''
    @api.onchange("producto", "cantidad")
    def onchange_variante(self):
        self.total = self.cantidad * self.precio_unidad
  
       
  
  