"""Al actualizar: cargar la clasificación de costes del asesor y limpiar el
detalle viejo del P&G (sus bloques ya no existen)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = env["lira.cuenta.bloque"]._sembrar()
        _logger.info("Clasificación de costes: %s cuentas cargadas.", n)
    except Exception as e:
        _logger.warning("Clasificación de costes: no se pudo sembrar: %s", e)
    try:
        env["lira.pnl.line"].search([]).unlink()
    except Exception:
        pass
