
from odoo import models, fields, api

import logging


_logger = logging.getLogger(__name__)
class CentroTrabajo(models.Model):
    _inherit = "mrp.workcenter"
    small_coste_hora = fields.Float(
        string="Pequeño - Coste Hora",
    )
    small_diametro = fields.Float(
        string="Diametro",
    )
    small_largo = fields.Float(
        string="Largo",
    )
    small_ancho = fields.Float(
        string="Ancho",
    )
    small_altura = fields.Float(
        string="Altura",
    )
    mediano_coste_hora = fields.Float(
        string="Mediano - Coste Hora",
    )
    mediano_diametro = fields.Float(
        string="Diametro",
    )
    mediano_largo = fields.Float(
        string="Largo",
    )
    mediano_ancho = fields.Float(
        string="Ancho",
    )
    mediano_altura = fields.Float(
        string="Altura",
    )
    grande_coste_hora = fields.Float(
        string="Grande - Coste Hora",
    )
    grande_diametro = fields.Float(
        string="Diametro",
    )
    grande_largo = fields.Float(
        string="Largo",
    )
    grande_ancho = fields.Float(
        string="Ancho",
    )
    grande_altura = fields.Float(
        string="Altura",
    )
    muy_grande_coste_hora = fields.Float(
        string="Muy grande - Coste Hora",
    )
    muy_grande_diametro = fields.Float(
        string="Diametro",
    )
    muy_grande_largo = fields.Float(
        string="Largo",
    )
    muy_grande_ancho = fields.Float(
        string="Ancho",
    )
    muy_grande_altura = fields.Float(
        string="Altura",
    )
   

   