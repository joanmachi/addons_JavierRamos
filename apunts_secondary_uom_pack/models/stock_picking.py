import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        # button_validate puede devolver un wizard (backorder, etc.). Lo
        # importante es que tras esta llamada los moves done están listos.
        # Procesamos los pickings que han pasado a 'done' o que tienen
        # algún move done.
        for picking in self:
            moves_done = picking.move_ids.filtered(lambda m: m.state == "done")
            if not moves_done:
                continue
            try:
                picking._apunts_propagar_secondary_uom(moves_done)
                picking._apunts_calibrar_factor_productos(moves_done)
            except Exception as e:
                # No bloquear la validación del picking por una recalibración
                _logger.warning(
                    "Apunts: post-validate sec uom falló en picking %s: %s",
                    picking.name,
                    e,
                )
        return res

    def _apunts_propagar_secondary_uom(self, moves_done):
        """Propaga los kg/m del operario al PO/sale line de origen.

        Los campos `apunts_qty_received_secondary` y `apunts_qty_delivered_secondary`
        son computed/stored — se recalculan solos por dependency. Esta función
        solo dispara una invalidación explícita por si hay edges no cubiertos.
        """
        purchase_lines = moves_done.mapped("purchase_line_id")
        sale_lines = moves_done.mapped("sale_line_id")
        if purchase_lines:
            purchase_lines.invalidate_recordset(["apunts_qty_received_secondary"])
        if sale_lines:
            sale_lines.invalidate_recordset(["apunts_qty_delivered_secondary"])

    def _apunts_calibrar_factor_productos(self, moves_done):
        """Auto-calibración del factor del product.secondary.unit por
        media móvil de las últimas 5 recepciones del producto en las que
        el operario rellenó tanto `quantity` (UdM primaria) como
        `secondary_uom_qty` (UdM secundaria).
        """
        # Solo nos interesan los moves del propio picking con sec_uom y datos
        # útiles (qty > 0 y sec_qty > 0).
        candidatos = moves_done.filtered(
            lambda m: m.secondary_uom_id
            and m.quantity > 0
            and m.secondary_uom_qty > 0
        )
        if not candidatos:
            return
        for producto, moves_prod in self._apunts_group_by_product(candidatos):
            for sec_uom in moves_prod.mapped("secondary_uom_id"):
                producto.product_tmpl_id._apunts_recalibrar_factor_secundario(sec_uom)

    @staticmethod
    def _apunts_group_by_product(moves):
        agrupado = {}
        for m in moves:
            agrupado.setdefault(m.product_id, m.browse())
            agrupado[m.product_id] |= m
        return agrupado.items()
