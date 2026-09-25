"""Nomenclatura (petición de dirección, 11-sep-2026): los ratios del P&G se
dividen por la facturación contabilizada (cuentas 70x), no por los pedidos de
venta. La fórmula no cambia; solo el nombre del concepto pasa de "sobre ventas"
a "sobre facturación" en el Panel, sus KPIs y los criterios de semáforo.
Además el Detalle de la cartera pasa a abrir la gráfica por semana de entrega
(se resiembra el catálogo para actualizar los textos de ayuda). La pregunta del
bloque 1 pasa a "al ritmo de facturación", que es lo que mide el CDC.."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

CRITERIOS = {
    "variables_pct": "Variables directos / facturación (%)",
    "semivariables_pct": "Semivariables / facturación (%)",
    "fijos_pct": "Fijos operativos / facturación (%)",
    "cov": "COV — Coste operativo s/ facturación (%)",
    "edv": "EDV — Estructura s/ facturación (%)",
    "amortizaciones_pct": "Amortizaciones / facturación (%)",
    "financieros_pct": "Gastos financieros / facturación (%)",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env["apunts.kpi.bloque"]._sembrar()  # reescribe nombres de bloques y KPIs
    except Exception as e:
        _logger.warning("Reunión semanal: no se pudo resembrar el catálogo: %s", e)
    for clave, name in CRITERIOS.items():
        cr.execute("UPDATE lira_ratio_criterio SET name = %s WHERE clave = %s", (name, clave))
    _logger.info("Reunión semanal: ratios renombrados a 'sobre facturación'.")
