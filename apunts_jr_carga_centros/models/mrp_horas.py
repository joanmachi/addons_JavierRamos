from odoo import api, fields, models


class MrpWorkcenterProductivity(models.Model):
    """Duración del fichaje en HORAS (almacenada) para que los paneles y
    pivotes se lean en horas y no en minutos (petición del cliente:
    'solo horas, nada de minutos en todos los paneles')."""

    _inherit = "mrp.workcenter.productivity"

    apunts_horas = fields.Float(
        string="Horas fichadas",
        compute="_compute_apunts_horas",
        store=True,
        aggregator="sum",
        help="Duración del fichaje en horas (minutos ÷ 60). Sirve para ver "
             "los pivotes y gráficas en horas en lugar de en minutos.",
    )

    @api.depends("duration")
    def _compute_apunts_horas(self):
        for p in self:
            p.apunts_horas = (p.duration or 0.0) / 60.0


class MrpWorkorder(models.Model):
    """Horas previstas y reales de la orden de trabajo (almacenadas), para los
    pivotes teórico-vs-real en horas en lugar de minutos."""

    _inherit = "mrp.workorder"

    apunts_horas_previstas = fields.Float(
        string="Horas previstas",
        compute="_compute_apunts_horas_wo",
        store=True,
        aggregator="sum",
        help="Duración prevista de la OT en horas (minutos ÷ 60).",
    )
    apunts_horas_reales = fields.Float(
        string="Horas reales",
        compute="_compute_apunts_horas_wo",
        store=True,
        aggregator="sum",
        help="Duración real fichada en la OT en horas (minutos ÷ 60).",
    )

    @api.depends("duration", "duration_expected")
    def _compute_apunts_horas_wo(self):
        for w in self:
            w.apunts_horas_previstas = (w.duration_expected or 0.0) / 60.0
            w.apunts_horas_reales = (w.duration or 0.0) / 60.0
