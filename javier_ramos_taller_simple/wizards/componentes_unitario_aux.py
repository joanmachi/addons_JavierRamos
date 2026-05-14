# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class ComponenteUnitarioAux(models.TransientModel):
    _name = "javier_ramos_taller_simple.componentes_unitario_aux"

    producto = fields.Many2one(
        'product.template',
        string='Producto',
        required = True,
    )
 


    @api.onchange("cuestionario_aux")
    def _compute_custom_producto_domain(self):
        for elemento in self:

            productos_1 = self.env['product.template'].search([('tipo_producto', '=', 'unitario')])
            productos_2 = self.env['product.template'].search([('tipo_producto', '=', 'serie')])
            productos_ids = productos_1.ids + productos_2.ids
            dominio = [('id', 'in', productos_ids)]
            elemento.custom_producto_domain = dominio
    custom_producto_domain = fields.Char(compute="_compute_custom_producto_domain")
  
    precio_unidad = fields.Float(
        string="Precio(Und.)", readonly=True, store=True
    )
    cantidad = fields.Float(string="Cantidad(Und.)",default=1)
    total = fields.Float(string="total")

    cuestionario_aux = fields.Many2one(
        'javier_ramos_taller_simple.cuestionario',
        string='Cuestionario'
    )

    @api.onchange("cantidad", "producto")
    def onchange_variante(self):
        _logger.info('---------- onchange_variante')
        context = dict(self.env.context or {})
        id_producto = context.get('producto')
        modelo_producto = context.get('modelo_producto')
        _logger.info('---------- id_producto')
        _logger.info(id_producto)
        _logger.info('---------- modelo_producto')
        _logger.info(modelo_producto)
        producto_principal = False
        if modelo_producto == 'product.product':
            producto_producto = self.env['product.product'].search([('id', '=', id_producto)], limit = 1)
            if not producto_producto:
                return
            producto_principal = producto_producto.product_tmpl_id
            
        
        if modelo_producto == 'product.template':
            producto_principal = self.env['product.template'].search([('id', '=', id_producto)], limit = 1)
         
        _logger.info(producto_principal)
        _logger.info(producto_principal.sale_order_line)
        if producto_principal and producto_principal.sale_order_line:
            precio_venta = self.producto.calcular_precio_venta((producto_principal.sale_order_line.product_uom_qty * self.cantidad))
            _logger.info(precio_venta)

            self.precio_unidad = precio_venta
        else:
            self.precio_unidad = self.producto.standard_price
        self.total = self.cantidad * self.precio_unidad

   
  