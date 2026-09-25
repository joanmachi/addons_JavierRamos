# -*- coding: utf-8 -*-
from odoo import api, fields, models


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

    def _apunts_enlazar_docs_taller(self):
        """El widget de subida deja los adjuntos con res_id = 0 (huérfanos), y Odoo
        solo deja abrir un adjunto huérfano a quien lo subió: en la tablet, el
        operario ve el PDF en la lista pero no puede abrirlo. Se enlazan al
        producto para que valgan los permisos normales de lectura del producto."""
        for tmpl in self:
            huerfanos = tmpl.apunts_docs_taller_ids.sudo().filtered(
                lambda a: not a.res_id or a.res_model != 'product.template')
            if huerfanos:
                huerfanos.write({'res_model': 'product.template', 'res_id': tmpl.id, 'res_field': False})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._apunts_enlazar_docs_taller()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'apunts_docs_taller_ids' in vals:
            self._apunts_enlazar_docs_taller()
        return res
