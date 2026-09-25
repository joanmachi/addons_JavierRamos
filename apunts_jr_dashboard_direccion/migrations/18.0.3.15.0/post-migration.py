"""MACPRE y MACOP cambian de definición (MACPRE toda la plantilla, MACOP solo
planta): se rehace su histórico entero con el criterio nuevo."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("DELETE FROM apunts_kpi_serie WHERE clave IN ('macpre', 'macop')")
    cr.execute("DELETE FROM apunts_kpi_semana WHERE clave IN ('macpre', 'macop')")
    n = env["apunts.kpi.motor"].reconstruir_historico()
    _logger.info("MACPRE/MACOP rehechos con el criterio nuevo (%s valores en total)", n)
