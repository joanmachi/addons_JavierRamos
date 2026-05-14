from collections import OrderedDict

from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def apunts_grouped_lines(self):
        """Devuelve líneas agrupadas SOLO de este picking, una por (producto, UoM).

        Garantiza que el PDF del albarán muestre EXACTAMENTE lo que físicamente
        está en este picking — sin sumar qty de pickings padre, sin contar
        backorders hijos, sin dividir por ubicación o lote.

        Se usa desde el template QWeb override.
        """
        self.ensure_one()
        grouped = OrderedDict()  # key = (product.id, uom.id)
        # Si está done, preferimos move_line_ids (lo realmente movido).
        # Si no, usamos move_ids (lo planificado).
        if self.state == "done" and self.move_line_ids:
            for ml in self.move_line_ids:
                if not ml.product_id:
                    continue
                key = (ml.product_id.id, (ml.product_uom_id or ml.move_id.product_uom).id)
                if key not in grouped:
                    grouped[key] = {
                        "product_id": ml.product_id,
                        "product_uom": ml.product_uom_id or ml.move_id.product_uom,
                        "qty": 0.0,
                        "qty_ordered": 0.0,
                    }
                grouped[key]["qty"] += ml.quantity or 0.0
                # qty_ordered del move padre (planificado)
                grouped[key]["qty_ordered"] = ml.move_id.product_uom_qty or grouped[key]["qty"]
        else:
            for m in self.move_ids:
                if not m.product_id or not m.product_uom_qty:
                    continue
                key = (m.product_id.id, m.product_uom.id)
                if key not in grouped:
                    grouped[key] = {
                        "product_id": m.product_id,
                        "product_uom": m.product_uom,
                        "qty": 0.0,
                        "qty_ordered": 0.0,
                    }
                grouped[key]["qty"] += m.quantity or 0.0
                grouped[key]["qty_ordered"] += m.product_uom_qty or 0.0
        return list(grouped.values())
