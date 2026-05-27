from odoo import fields, models


class ApuntsJrCostesCadena(models.TransientModel):
    _name = 'apunts.jr.costes.cadena'
    _description = 'Costes consolidados — cadena de OFs parciales'

    production_id = fields.Many2one('mrp.production', readonly=True)
    of_ids = fields.Many2many('mrp.production', string='OFs de la cadena', readonly=True)
    raiz_name = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    cadena_sale_amount = fields.Monetary(
        string='Venta (€)', currency_field='currency_id', readonly=True,
    )
    cadena_cost_total_real = fields.Monetary(
        string='En curso real (€)', currency_field='currency_id', readonly=True,
    )
    cadena_cost_total_planned = fields.Monetary(
        string='Coste teórico (€)', currency_field='currency_id', readonly=True,
    )
    cadena_mat_real = fields.Monetary(
        string='MP real (€)', currency_field='currency_id', readonly=True,
    )
    cadena_mat_planned = fields.Monetary(
        string='MP teórica (€)', currency_field='currency_id', readonly=True,
    )
    cadena_mo_real = fields.Monetary(
        string='MO real (€)', currency_field='currency_id', readonly=True,
    )
    cadena_mo_planned = fields.Monetary(
        string='MO teórica (€)', currency_field='currency_id', readonly=True,
    )
    cadena_machine_real = fields.Monetary(
        string='Máquina real (€)', currency_field='currency_id', readonly=True,
    )
    cadena_machine_planned = fields.Monetary(
        string='Máquina teórica (€)', currency_field='currency_id', readonly=True,
    )
    cadena_min_real = fields.Float(string='Tiempo real (min)', readonly=True)
    cadena_min_planned = fields.Float(string='Tiempo teórico (min)', readonly=True)
    cadena_margin = fields.Monetary(
        string='Margen (€)', currency_field='currency_id', readonly=True,
    )
    cadena_margin_state = fields.Char(readonly=True)
