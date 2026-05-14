"""Hito 11 - Override manual del campo Studio venta desde Settings.

Si la auto-deteccion del helper `_apunts_get_studio_sale_field` falla o el cliente
quiere forzar un campo concreto, se setea desde Manufacturing > Configuracion >
Apunts Costes OF y se persiste en `ir.config_parameter`
'apunts_costes_of.studio_sale_field'.

Valor especial '__none__' = override manual para deshabilitar la auto-deteccion
(util si el cliente NO usa Studio y queremos evitar que el modulo siga buscando).
"""
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    apunts_studio_sale_field = fields.Char(
        string='Campo Studio venta (mrp.production)',
        config_parameter='apunts_costes_of.studio_sale_field',
        help=(
            'Nombre tecnico del campo m2o(sale.order) anyadido via Studio en mrp.production '
            '(ej. "x_studio_venta" en JR). Si vacio, el modulo intenta auto-detectarlo al '
            'instalar/actualizar buscando un m2o(sale.order) con prefijo x_studio_ o x_. '
            'Para deshabilitar la auto-deteccion definitivamente, escribe "__none__".'
        ),
    )
