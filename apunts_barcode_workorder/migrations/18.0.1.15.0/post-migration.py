"""Documentos de taller huérfanos (res_id 0): enlazarlos a su producto para
que los operarios puedan abrirlos desde la tablet."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_attachment a
           SET res_model = 'product.template', res_id = r.product_tmpl_id, res_field = NULL
          FROM apunts_product_doc_taller_rel r
         WHERE r.attachment_id = a.id
           AND (a.res_id IS NULL OR a.res_id = 0 OR a.res_model IS DISTINCT FROM 'product.template')""")
    _logger.info("Documentos de taller enlazados a su producto: %d", cr.rowcount)
