# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class Servicios(models.TransientModel):
    _name = "javier_ramos_taller_simple.servicios"

    producto = fields.Many2one(
        'product.template',
        string='Servicio',
        required = True,
        domain = [('categ_id.name', '=', 'SERVICIOS SUBCONTRATADOS')]
    )




    
    producto_principal = fields.Many2one(
        'product.template',
        string='Producto'
    )
    precio_unidad = fields.Float(
        string="Precio(m²)", readonly=True, store=True
    )
    cantidad = fields.Float(string="Cantidad(m²)",default=1, digits=(16, 4))
    total = fields.Float(string="Total")
    tiempo_esperado = fields.Float(string="Tiempo esperado",default=5)

    tipo_producto = fields.Selection(related='producto_principal.tipo_producto',
        selection= [('unitario', 'Unitario'),('serie', 'Serie'),('conjunto', 'Conjunto')]
    )



    @api.onchange("producto", "cantidad")
    def onchange_producto(self):
        self.total = self.cantidad * self.precio_unidad
  