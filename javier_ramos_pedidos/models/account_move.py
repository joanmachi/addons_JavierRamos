# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_due_date_display = fields.Date(
        string='Fecha Vencimiento',
        related='invoice_date_due',
        store=True,
    )
