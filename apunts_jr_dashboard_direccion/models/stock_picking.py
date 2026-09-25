from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    apunts_fecha_limite = fields.Datetime(
        string="Fecha comprometida",
        compute="_compute_apunts_en_fecha",
        store=True,
        help=(
            "Fecha de entrega comprometida en el pedido de venta origen. "
            "Solo en albaranes de salida; vacía si no se comprometió fecha."
        ),
    )
    apunts_en_fecha = fields.Boolean(
        string="Entregado en fecha",
        compute="_compute_apunts_en_fecha",
        store=True,
        help=(
            "True si el albarán de salida se validó en o antes de la fecha "
            "comprometida del pedido de venta."
        ),
    )

    apunts_dias_desvio = fields.Float(
        string="Desvío (días)",
        compute="_compute_apunts_en_fecha",
        store=True,
        digits=(16, 1),
        aggregator="avg",
        help=(
            "Días entre la fecha comprometida y la entrega real: positivo = se "
            "entregó tarde, negativo = antes de tiempo, 0 = el mismo día. En las "
            "gráficas se muestra la media."
        ),
    )
    apunts_dias_retraso = fields.Float(
        string="Retraso (días)",
        compute="_compute_apunts_en_fecha",
        store=True,
        digits=(16, 1),
        aggregator="avg",
        help="Solo los días de más: 0 si se entregó en fecha o antes.",
    )

    @api.depends(
        "sale_id.commitment_date",
        "date_done",
        "state",
        "picking_type_id.code",
    )
    def _compute_apunts_en_fecha(self):
        for picking in self:
            # Solo cuenta la fecha COMPROMETIDA con el cliente. Un pedido sin
            # fecha comprometida no se puede medir (queda fuera del KPI).
            limite = False
            if picking.picking_type_id.code == "outgoing" and picking.sale_id:
                limite = picking.sale_id.commitment_date
            picking.apunts_fecha_limite = limite
            entregado = bool(limite and picking.state == "done" and picking.date_done)
            desvio = (picking.date_done.date() - limite.date()).days if entregado else 0
            picking.apunts_en_fecha = bool(entregado and desvio <= 0)
            picking.apunts_dias_desvio = float(desvio) if entregado else 0.0
            picking.apunts_dias_retraso = float(max(desvio, 0)) if entregado else 0.0

    # ── Recepciones: cumplimiento de proveedores (Xavi/Cinthia, 22/09/2026) ──
    apunts_prov_programada = fields.Date(
        string="Fecha programada", compute="_compute_apunts_proveedor", store=True,
        help="Fecha prevista de llegada: la del pedido de compra (fecha límite del albarán) "
             "o, si no la tiene, la fecha programada del albarán.",
    )
    apunts_prov_efectiva = fields.Date(
        string="Fecha efectiva", compute="_compute_apunts_proveedor", store=True,
        help="Día en que se validó la recepción y el material entró en stock.",
    )
    apunts_prov_retraso = fields.Float(
        string="Retraso (días)", compute="_compute_apunts_proveedor", store=True,
        digits=(16, 1), aggregator="avg",
        help="Efectiva − programada. Positivo = llegó tarde; negativo = antes de lo previsto.",
    )
    apunts_prov_en_fecha = fields.Boolean(
        string="Recibido en fecha", compute="_compute_apunts_proveedor", store=True,
    )
    apunts_prov_en_fecha_pct = fields.Float(
        string="% en fecha", compute="_compute_apunts_proveedor", store=True,
        digits=(16, 1), aggregator="avg",
        help="100 si llegó en fecha, 0 si no. Agrupado por proveedor da su porcentaje de cumplimiento.",
    )

    @api.depends("date_deadline", "scheduled_date", "date_done", "state", "picking_type_id.code", "return_id")
    def _compute_apunts_proveedor(self):
        for picking in self:
            es_recepcion = (picking.picking_type_id.code == "incoming" and picking.state == "done"
                            and picking.date_done and not picking.return_id)
            prevista = picking.date_deadline or picking.scheduled_date
            if not es_recepcion or not prevista:
                picking.apunts_prov_programada = False
                picking.apunts_prov_efectiva = False
                picking.apunts_prov_retraso = 0.0
                picking.apunts_prov_en_fecha = False
                picking.apunts_prov_en_fecha_pct = 0.0
                continue
            retraso = (picking.date_done.date() - prevista.date()).days
            picking.apunts_prov_programada = prevista.date()
            picking.apunts_prov_efectiva = picking.date_done.date()
            picking.apunts_prov_retraso = float(retraso)
            picking.apunts_prov_en_fecha = retraso <= 0
            picking.apunts_prov_en_fecha_pct = 100.0 if retraso <= 0 else 0.0
