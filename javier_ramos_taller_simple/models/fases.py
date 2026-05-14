# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import Command,api, fields, models, _
from odoo.exceptions import ValidationError


import logging


_logger = logging.getLogger(__name__)
class Fases(models.TransientModel):
    _name = "javier_ramos_taller_simple.fases"
    operacion = fields.Char(
        string='Operación',
        required = True,
    )
    num_fases = fields.Integer(
        string='Fases',
        default = 1,
        required = True,
    )
    centro_trabajo = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        required = True,
    )
    minutos = fields.Float(string="Minutos",required = True)

    producto_principal = fields.Many2one(
        'product.template',
        string='Producto'
    )

    ignorar_preparacion_limpieza = fields.Boolean(
 
        string="Ignorar preparación y limpieza"
    )
  