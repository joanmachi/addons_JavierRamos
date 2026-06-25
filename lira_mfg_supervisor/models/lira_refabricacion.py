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
    # Compras de material generadas para reponer estas piezas (una por proveedor).
    purchase_order_ids = fields.Many2many(
        'purchase.order', 'lira_refab_po_rel', 'refab_id', 'po_id',
        string='Compras de reposición', copy=False)
    recibido = fields.Boolean(
        string='Material recibido', compute='_compute_recibido', store=True,
        help='El material comprado para reponer estas piezas ya ha llegado '
             '(todas las compras de reposición están totalmente recibidas). '
             'Hasta entonces las piezas quedan pendientes de recepción.')

    @api.depends('purchase_order_ids.order_line.qty_received',
                 'purchase_order_ids.order_line.product_qty',
                 'purchase_order_ids.state')
    def _compute_recibido(self):
        for rec in self:
            pos = rec.purchase_order_ids.filtered(lambda p: p.state != 'cancel')
            if rec.accion != 'reposicion' or not pos:
                # Retrabajo (sin compra) o sin compras vinculadas: no bloquea.
                rec.recibido = True
                continue
            lineas = pos.order_line
            rec.recibido = bool(lineas) and all(
                (l.qty_received or 0.0) >= (l.product_qty or 0.0) for l in lineas
            )
    # Fases de retrabajo creadas para estas piezas (solo si accion=retrabajo).
    workorder_retrabajo_ids = fields.Many2many(
        'mrp.workorder', 'lira_refab_wo_rel', 'refab_id', 'wo_id',
        string='Fases de retrabajo', copy=False)
    motivo = fields.Selection(
        MOTIVOS_REFABRICACION, string='Motivo', required=True, index=True)
    supervisor_id = fields.Many2one(
        'res.users', string='Validado por', default=lambda self: self.env.user)
    fecha = fields.Datetime(string='Fecha', default=fields.Datetime.now, index=True)
