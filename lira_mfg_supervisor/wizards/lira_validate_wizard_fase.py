from odoo import fields, models


class LiraValidateWizardFase(models.TransientModel):
    _name = 'lira.validate.wizard.fase'
    _description = 'Fase de retrabajo (wizard de validación)'
    _order = 'secuencia, id'

    wizard_id = fields.Many2one(
        'lira.validate.wizard', required=True, ondelete='cascade')
    nombre = fields.Char(string='Nombre de la fase', required=True)
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Centro de trabajo', required=True)
    secuencia = fields.Integer(default=10)
