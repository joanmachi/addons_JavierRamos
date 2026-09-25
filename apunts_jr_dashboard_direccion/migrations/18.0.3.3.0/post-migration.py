"""MACPRE con el nuevo criterio de personal de planta: se rehace su histórico."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env["apunts.kpi.semana"].with_context(apunts_kpi_forzar=True).search(
            [("clave", "=", "macpre")]).unlink()
        env["apunts.kpi.motor"].reconstruir_historico()
        _logger.info("MACPRE rehecho con el criterio de planta.")
    except Exception as e:
        _logger.warning("No se pudo rehacer el MACPRE: %s", e)
