"""Al actualizar a 18.0.3.0.0: montar la reunión semanal de Dirección.

Crea los 6 indicadores y sus KPIs, carga los criterios de aceptación del
informe de la empresa (sin pisar los que ya hayan editado), estima los pagos
recurrentes del DAT y reconstruye el histórico semanal del año con lo que hay
en Odoo. A partir de aquí, cada lunes se cierra la semana sola."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = env["apunts.kpi.bloque"]._sembrar()
        _logger.info("Reunión semanal: %s KPIs en el catálogo.", n)
    except Exception as e:
        _logger.warning("Reunión semanal: no se pudo sembrar el catálogo: %s", e)
    try:
        env["apunts.dat.pago"]._sembrar()
    except Exception as e:
        _logger.warning("Reunión semanal: no se pudieron estimar los pagos del DAT: %s", e)
    try:
        n = env["apunts.kpi.motor"].reconstruir_historico()
        _logger.info("Reunión semanal: histórico reconstruido (%s valores).", n)
    except Exception as e:
        _logger.warning("Reunión semanal: no se pudo reconstruir el histórico: %s", e)
