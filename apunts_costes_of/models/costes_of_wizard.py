from odoo import models, fields


class ApuntsCostesOfDesgloseWizard(models.TransientModel):
    _name = 'apunts.costes.of.desglose.wizard'
    _description = 'Checkpoint de costes OF — desglose en tiempo real'

    production_id = fields.Many2one('mrp.production', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', related='production_id.currency_id', readonly=True)

    # Material
    material_presupuestado = fields.Monetary(
        'MP presupuestada', currency_field='currency_id', readonly=True,
        help='Coste material segun BoM x cantidad OF.')
    material_consumido = fields.Monetary(
        'MP consumida', currency_field='currency_id', readonly=True,
        help='Coste material ya consumido (moves done).')
    material_restante = fields.Monetary(
        'MP restante', currency_field='currency_id', readonly=True,
        help='Estimado pendiente: max(0, presupuestado - consumido).')

    # Mano de obra
    labor_presupuestado = fields.Monetary(
        'MO presupuestada', currency_field='currency_id', readonly=True,
        help='Coste mano de obra segun routing BoM.')
    labor_imputado = fields.Monetary(
        'MO imputada', currency_field='currency_id', readonly=True,
        help='Coste laboral real imputado (productivity entries x hourly_cost empleado).')

    # Centros de trabajo
    centros_presupuestado = fields.Monetary(
        'Centros presupuestados', currency_field='currency_id', readonly=True,
        help='Coste centros segun routing BoM (costs_hour x horas estimadas).')
    centros_imputado = fields.Monetary(
        'Centros imputados', currency_field='currency_id', readonly=True,
        help='Coste centros real imputado (productivity entries x costs_hour centro).')

    # Totales
    total_presupuestado = fields.Monetary(
        'Total presupuestado', currency_field='currency_id', readonly=True,
        help='MP + MO + Centros presupuestados.')
    total_actual = fields.Monetary(
        'Total actual', currency_field='currency_id', readonly=True,
        help='MP consumida + MO imputada + Centros imputados.')
    total_restante = fields.Monetary(
        'Restante estimado', currency_field='currency_id', readonly=True,
        help='max(0, total presupuestado - total actual). Estimado que falta por imputar.')

    # Lineas detalladas (related a mrp.production)
    material_line_ids = fields.One2many(
        related='production_id.apunts_material_line_ids', readonly=True,
        string='Componentes')
    labor_line_ids = fields.One2many(
        related='production_id.apunts_labor_line_ids', readonly=True,
        string='Operaciones / centros')
