# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class ComponenteUnitario(models.TransientModel):
    _name = "javier_ramos_taller_simple.componentes_unitario"

    producto = fields.Many2one(
        'product.template',
        string='Producto',
        required = True,
    )



            
    @api.onchange("producto_principal")
    def _compute_custom_producto_domain(self):
        for elemento in self:
            dominio = []
      
            productos_1 = self.env['product.template'].search([('tipo_producto', '=', 'unitario')])
            productos_2 = self.env['product.template'].search([('tipo_producto', '=', 'serie')])
            productos_ids = productos_1.ids + productos_2.ids
            dominio = [('id', 'in', productos_ids)]
            elemento.custom_producto_domain = dominio
               
    custom_producto_domain = fields.Char(compute="_compute_custom_producto_domain")

    cantidad = fields.Float(string="Cantidad(Und.)",default=1, digits=(16, 4))
    tiempo_recepcion = fields.Float(string="Tiempo recepción",default=7)
    producto_principal = fields.Many2one(
        'product.template',
        string='Producto'
    )

    precio_unidad = fields.Float(
        string="Precio(Und.)", store=True
    )
    total = fields.Float(string="total")


    @api.onchange("cantidad", "producto", 'precio_unidad')
    def onchange_variante(self):
        

        self.total = self.cantidad * self.precio_unidad
  
  