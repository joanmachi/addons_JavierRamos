import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Al actualizar: retro-alimentar la evolución de carga con los últimos
    90 días (estimación por fechas de creación/cierre de OTs) y tomar la
    primera foto real de hoy. Se ejecuta una sola vez."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Snapshot = env["apunts.carga.snapshot"]
    creadas = Snapshot.generar_historico_estimado(dias=90)
    Snapshot.cron_tomar_foto()
    _logger.info(
        "apunts_jr_carga_centros: backfill de evolución de carga hecho "
        "(%s filas estimadas + foto de hoy).",
        creadas,
    )
