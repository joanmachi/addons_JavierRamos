import logging

from odoo import models

_logger = logging.getLogger(__name__)

APUNTS_CALIBRACION_VENTANA = 5  # nº últimas recepciones para la media móvil


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _apunts_recalibrar_factor_secundario(self, secondary_uom):
        """Recalibra el factor de `secondary_uom` para este product.template
        usando media móvil de las últimas N recepciones (`stock.move` done)
        en las que el operario rellenó tanto la UdM primaria como la
        secundaria del mismo producto.

        Factor del módulo OCA `product_secondary_unit`:
            primary_qty = secondary_qty * factor

        Por tanto:
            factor_medido = move.quantity / move.secondary_uom_qty
        (primaria / secundaria)
        """
        self.ensure_one()
        if not secondary_uom or secondary_uom.product_tmpl_id != self:
            return False

        Move = self.env["stock.move"]
        moves_validos = Move.sudo().search(
            [
                ("product_id.product_tmpl_id", "=", self.id),
                ("state", "=", "done"),
                ("secondary_uom_id", "=", secondary_uom.id),
                ("quantity", ">", 0),
                ("secondary_uom_qty", ">", 0),
            ],
            order="date DESC, id DESC",
            limit=APUNTS_CALIBRACION_VENTANA,
        )
        if not moves_validos:
            return False

        factores = [
            m.quantity / m.secondary_uom_qty
            for m in moves_validos
            if m.secondary_uom_qty
        ]
        if not factores:
            return False

        nuevo_factor = sum(factores) / len(factores)
        if nuevo_factor <= 0:
            return False

        viejo_factor = secondary_uom.factor
        secondary_uom.sudo().write({"factor": nuevo_factor})
        _logger.info(
            "Apunts auto-calibración: producto '%s' sec '%s' factor %s → %s "
            "(media de %s recepciones)",
            self.name,
            secondary_uom.code,
            viejo_factor,
            nuevo_factor,
            len(factores),
        )
        return True
