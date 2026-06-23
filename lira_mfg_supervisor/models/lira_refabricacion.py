from odoo import api, fields, models

# Motivos de calidad por los que unas piezas no se validan y van a
# retrabajo o reposición. Se comparte con el wizard de validación.
MOTIVOS_REFABRICACION = [
    ('mala_interpretacion', 'Mala interpretación de instrucciones'),
    ('fallos_medios', 'Fallos medios producción'),
    ('mala_ejecucion', 'Mala ejecución'),
    ('error_programacion', 'Error de programación'),
]


class LiraRefabricacionLinea(models.Model):
    _name = 'lira.refabricacion.linea'
    _description = 'Trazabilidad de piezas rectificadas (retrabajo / reposición)'
    _order = 'fecha desc, id desc'

    workorder_id = fields.Many2one(
        'mrp.workorder', string='Fase (OT)', required=True, ondelete='cascade', index=True)
    production_id = fields.Many2one(
        'mrp.production', string='Orden de Fabricación', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Producto', related='production_id.product_id', store=True)
    employee_ids = fields.Many2many(
        'hr.employee', string='Operarios',
        help='Operarios que registraron piezas en esta fase (los que estaban '
             'fichados). Pueden ser varios; el responsable de validación '
             'determina a quién atribuir la rectificación.')
    qty = fields.Float(string='Uds. rectificadas', digits=(16, 2))
    accion = fields.Selection([
        ('retrabajo', 'Retrabajo'),
        ('reposicion', 'Reposición'),
    ], string='Acción', required=True)
    motivo = fields.Selection(
        MOTIVOS_REFABRICACION, string='Motivo', required=True, index=True)
    supervisor_id = fields.Many2one(
        'res.users', string='Validado por', default=lambda self: self.env.user)
    fecha = fields.Datetime(string='Fecha', default=fields.Datetime.now, index=True)
