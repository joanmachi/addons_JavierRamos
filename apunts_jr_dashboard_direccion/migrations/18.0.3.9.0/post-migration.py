"""El DAT ya se calcula a una fecha (pendiente según lo conciliado hasta
entonces), así que su histórico semanal se puede reconstruir: se borra la
única foto que había y se rehace desde el principio del año."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env["apunts.kpi.semana"].with_context(apunts_kpi_forzar=True).search(
            [("clave", "=", "dat")]).unlink()
        env["apunts.kpi.motor"].reconstruir_historico()
        _logger.info("DAT: histórico semanal reconstruido.")
    except Exception as e:
        _logger.warning("No se pudo reconstruir el histórico del DAT: %s", e)
