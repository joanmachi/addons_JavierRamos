from odoo import models, fields, api


class LiraVariableAccount(models.Model):
    _name = 'lira.variable.account'
    _description = 'Cuenta contable marcada como Coste Variable'
    _order = 'code'

    code            = fields.Char('Código cuenta', required=True, index=True,
        help='Código contable de la cuenta que se considera un coste variable. Ejemplos PGC: 60010005 (compras de mercaderías), 601007 (materias primas), 6070002 (subcontratas), 62800001 (suministros).')
    name            = fields.Char('Nombre', compute='_compute_name_from_account', store=True,
        help='Nombre de la cuenta (se resuelve automáticamente desde el plan contable cuando coincide el código).')
    descripcion     = fields.Text('Por qué es variable',
        help='Motivo por el que esta cuenta se considera un coste variable. Útil para justificarlo ante el contable o auditor.')
    active          = fields.Boolean('Activa', default=True,
        help='Solo las cuentas activas se incluyen como variables en el P&G y en la Valoración de Inventario.')
    account_id      = fields.Many2one('account.account', compute='_compute_account_id', store=False,
        help='Enlace al registro real de la cuenta contable. Vacío si el código no existe en el plan contable de la empresa.')
    account_type    = fields.Selection(related='account_id.account_type', string='Tipo', store=False)
    company_id      = fields.Many2one('res.company', default=lambda s: s.env.company)

    _sql_constraints = [
        ('code_company_uniq', 'UNIQUE(code, company_id)',
         'Ya existe una cuenta variable con ese código en esta empresa.'),
    ]

    @api.depends('code', 'company_id')
    def _compute_name_from_account(self):
        for rec in self:
            acc = self.env['account.account'].search([
                ('code', '=', rec.code),
                ('company_ids', 'in', rec.company_id.id),
            ], limit=1) if rec.code else False
            rec.name = acc.name if acc else (rec.code or '')

    @api.depends('code', 'company_id')
    def _compute_account_id(self):
        for rec in self:
            rec.account_id = self.env['account.account'].search([
                ('code', '=', rec.code),
                ('company_ids', 'in', rec.company_id.id),
            ], limit=1) if rec.code else False

    def action_open_account(self):
        """Abre la ficha de la cuenta contable si existe."""
        self.ensure_one()
        if not self.account_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cuenta contable — {self.code}',
            'res_model': 'account.account',
            'res_id': self.account_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def get_variable_codes(self):
        """Devuelve los códigos activos. Si no hay registros, usa fallback."""
        codes = self.search([('active', '=', True)]).mapped('code')
        if not codes:
            # Fallback: las 7 cuentas originales marcadas por el contable
            return [
                '60010005', '601007', '6070002', '6070003',
                '600017', '6000018', '62800001',
            ]
        return codes
