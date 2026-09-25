"""Cartera pendiente de servir repartida en el tiempo (petición de dirección,
11-sep-2026): el botón Detalle del KPI abre directamente la gráfica que reparte
los euros pendientes por semana de entrega comprometida, para ver cuándo se va
a entregar lo vendido. Reutiliza las líneas del informe "Pedidos pendientes de
entrega" de lira (misma cifra que el KPI) y les añade la situación respecto a
hoy, para que en la gráfica se vea de un vistazo lo que ya va tarde."""
from datetime import timedelta

from odoo import api, fields, models


class LiraPendingDeliveryLine(models.Model):
    _inherit = "lira.pending.delivery.line"

    situacion = fields.Selection(
        [("vencida", "Fecha ya pasada"), ("semana", "Esta semana"),
         ("futura", "Próximas semanas"), ("sin_fecha", "Sin fecha comprometida")],
        string="Situación", compute="_compute_situacion", store=True,
        help="Fecha de entrega comprometida del pedido respecto a hoy.")

    @api.depends("fecha_entrega")
    def _compute_situacion(self):
        hoy = fields.Date.context_today(self)
        domingo = hoy + timedelta(days=6 - hoy.weekday())
        for linea in self:
            f = linea.fecha_entrega
            if not f:
                linea.situacion = "sin_fecha"
            elif f < hoy:
                linea.situacion = "vencida"
            elif f <= domingo:
                linea.situacion = "semana"
            else:
                linea.situacion = "futura"
