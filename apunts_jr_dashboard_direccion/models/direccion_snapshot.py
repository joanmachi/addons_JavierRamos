import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

KPIS = [
    ("fact_anual", "Facturación año (€)"),
    ("fact_semana", "Facturación semana (€)"),
    ("pedidos_mes", "Pedidos del mes (€)"),
    ("cartera_pendiente", "Cartera pendiente (€)"),
    ("cobertura_meses", "Cobertura (meses)"),
    ("tesoreria", "Tesorería (€)"),
    ("cobros_pendientes", "Cobros pendientes (€)"),
    ("margen_bruto", "Margen bruto año (€)"),
    ("margen_bruto_pct", "Margen bruto (%)"),
    ("entregas_mes_pct", "Entregas en fecha mes (%)"),
    ("horas_prod_pct", "Jornada cumplida (%)"),
    ("wip_valor", "Valor WIP (€)"),
]


class ApuntsDireccionSnapshot(models.Model):
    """Foto semanal de los KPIs de dirección, para la evolución histórica.
    Los KPIs tipo foto (tesorería, WIP, cartera, cobertura...) no se pueden
    reconstruir hacia atrás: la historia empieza cuando se instala esto."""

    _name = "apunts.direccion.snapshot"
    _description = "Foto semanal de KPIs de dirección"
    _order = "fecha desc, kpi"

    fecha = fields.Date(required=True, index=True)
    kpi = fields.Selection(KPIS, required=True, index=True)
    valor = fields.Float(digits=(16, 2))

    _sql_constraints = [
        ("fecha_kpi_uniq", "unique(fecha, kpi)", "Ya existe la foto de ese KPI para ese día.")
    ]

    @api.model
    def cron_tomar_foto(self):
        hoy = fields.Date.context_today(self)
        resumen = self.env["apunts.direccion.resumen"].create({})
        self.search([("fecha", "=", hoy)]).unlink()
        vals = []
        for campo, _label in KPIS:
            try:
                vals.append(
                    {"fecha": hoy, "kpi": campo, "valor": float(resumen[campo] or 0.0)}
                )
            except Exception as e:
                _logger.warning("Foto dirección: KPI %s falló: %s", campo, e)
        if vals:
            self.create(vals)
        _logger.info("Foto semanal de dirección tomada (%s KPIs).", len(vals))
