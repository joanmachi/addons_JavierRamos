from odoo import fields, models


class LiraRetrabajoPlantilla(models.Model):
    _name = 'lira.retrabajo.plantilla'
    _description = 'Plantilla de fases de retrabajo'
    _order = 'name'

    name = fields.Char(string='Nombre de la plantilla', required=True)
    linea_ids = fields.One2many(
        'lira.retrabajo.plantilla.linea', 'plantilla_id', string='Fases')


class LiraRetrabajoPlantillaLinea(models.Model):
    _name = 'lira.retrabajo.plantilla.linea'
    _description = 'Fase de plantilla de retrabajo'
    _order = 'secuencia, id'

    plantilla_id = fields.Many2one(
        'lira.retrabajo.plantilla', required=True, ondelete='cascade')
    nombre = fields.Char(string='Nombre de la fase', required=True)
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Centro de trabajo', required=True)
    secuencia = fields.Integer(default=10)
