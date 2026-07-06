import logging

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    apunts_tiene_uom_secundaria = fields.Boolean(
        compute="_compute_apunts_tiene_uom_secundaria",
        help="True si es una recepción con algún material por peso (kg). "
        "Controla la leyenda de ayuda en el formulario.",
    )

    @api.depends("move_ids.secondary_uom_id", "picking_type_code")
    def _compute_apunts_tiene_uom_secundaria(self):
        for picking in self:
            picking.apunts_tiene_uom_secundaria = (
                picking.picking_type_code == "incoming"
                and any(m.secondary_uom_id for m in picking.move_ids)
            )

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
                picking._apunts_ajustar_po_a_lo_recibido(moves_done)
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

    def _apunts_ajustar_po_a_lo_recibido(self, moves_done):
        """Al terminar la recepción, el pedido de compra se ajusta SOLO a
        lo realmente recibido (kg pesados + metros medidos por el operario):

        - `secondary_uom_qty` (kg) y `product_qty` (m) de la línea pasan a
          ser los valores reales.
        - `apunts_factor_linea` se sustituye por el ratio real m/kg, de modo
          que facturas y cantidades facturadas cuadran exactas.
        - `apunts_cantidades_reales` = True: a partir de aquí el sistema NO
          vuelve a recalcular una cantidad desde la otra (las correcciones
          manuales posteriores se respetan).

        Solo se ajusta cuando la línea no tiene NADA pendiente de recibir
        (para no romper recepciones parciales / backorders en curso).
        """
        lines = moves_done.mapped("purchase_line_id").filtered("secondary_uom_id")
        for line in lines:
            pendientes = line.move_ids.filtered(
                lambda m: m.state not in ("done", "cancel")
            )
            if pendientes:
                continue
            kg_real = line.apunts_qty_received_secondary
            m_real = line.qty_received
            if kg_real <= 0 or m_real <= 0:
                continue
            prec = line.product_uom.rounding or 0.01
            prec_sec = line.secondary_uom_id.uom_id.rounding or 0.01
            sin_cambios = (
                float_compare(line.product_qty, m_real, precision_rounding=prec) == 0
                and float_compare(
                    line.secondary_uom_qty, kg_real, precision_rounding=prec_sec
                )
                == 0
            )
            if sin_cambios and line.apunts_cantidades_reales:
                continue
            kg_antes = line.secondary_uom_qty
            m_antes = line.product_qty
            line.write(
                {
                    "secondary_uom_qty": kg_real,
                    "product_qty": m_real,
                    "apunts_factor_linea": m_real / kg_real,
                    "apunts_cantidades_reales": True,
                }
            )
            if not sin_cambios:
                uom_sec = line.secondary_uom_id.uom_id.name or ""
                uom_prim = line.product_uom.name or ""
                line.order_id.message_post(
                    body=Markup(
                        "⚖️ <b>%s</b>: pedido ajustado a lo recibido en %s — "
                        "%.2f %s → <b>%.2f %s</b> · %.2f %s → <b>%.2f %s</b>."
                    )
                    % (
                        line.product_id.display_name,
                        self.name,
                        kg_antes,
                        uom_sec,
                        kg_real,
                        uom_sec,
                        m_antes,
                        uom_prim,
                        m_real,
                        uom_prim,
                    )
                )

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
