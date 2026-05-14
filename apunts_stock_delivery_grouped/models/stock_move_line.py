from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_properties(self, move_line=False, move=False):
        """Override: simplifica `line_key` para agrupar move_lines del mismo
        producto + UdM en UNA SOLA FILA del PDF del albarán.
        """
        res = super()._get_aggregated_properties(move_line=move_line, move=move)
        move_real = move or (move_line and move_line.move_id) or self.env["stock.move"]
        product = move_real.product_id
        uom = move_real.product_uom or (move_line and move_line.product_uom_id)
        res["line_key"] = f"{product.id}_{uom.id}"
        res["description"] = ""
        res["packaging"] = self.env["product.packaging"]
        return res

    def _get_aggregated_product_quantities(self, **kwargs):
        """Forzar `strict=True` para que el cálculo de `qty_ordered` NO
        navegue backorders hijos ni sume qty de moves del picking padre.

        Sin esto, al imprimir un albarán que es backorder de otro (o que
        tiene backorders propios), aparecen líneas extra con cantidades
        de OTROS pickings (típico: 4 entregadas en el padre + 7 pendientes
        en backorder hijo, mostradas como 2 filas en el PDF del actual).

        Con strict=True el report muestra SOLO lo que físicamente está en
        ESTE picking — que es lo que el cliente espera ver en el albarán.
        """
        kwargs["strict"] = True
        return super()._get_aggregated_product_quantities(**kwargs)
