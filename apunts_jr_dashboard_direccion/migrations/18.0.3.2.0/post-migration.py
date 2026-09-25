"""Facturación unificada (ingresos contables 70x) en todas las pantallas:
se rehacen los históricos que la usaban con la definición antigua."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        Semana = env["apunts.kpi.semana"].with_context(apunts_kpi_forzar=True)
        Semana.search([("clave", "in", ("fact_semana", "pedidos_semana", "cdc"))]).unlink()
        env["apunts.kpi.motor"].reconstruir_historico()
        _logger.info("Facturación unificada: histórico de KPIs rehecho.")
    except Exception as e:
        _logger.warning("Facturación unificada: no se pudo rehacer el histórico de KPIs: %s", e)
    try:
        env["apunts.cmi.semana"].reconstruir_historico()
        _logger.info("Facturación unificada: registro semanal CMI rehecho.")
    except Exception as e:
        _logger.warning("Facturación unificada: no se pudo rehacer el CMI: %s", e)
