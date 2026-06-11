# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    apunts_docs_taller_ids = fields.Many2many(
        'ir.attachment',
        'apunts_product_doc_taller_rel',
        'product_tmpl_id',
        'attachment_id',
        string='Documentos de taller',
        help='Documentos (PDF, planos, instrucciones) que se podrán abrir desde '
             'la tablet en la vista de código de barras al pulsar el nombre del '
             'producto fabricado.',
    )
