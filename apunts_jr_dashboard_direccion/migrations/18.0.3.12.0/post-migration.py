"""Histórico semanal comparable entre semanas.

· Cartera pendiente y cobertura de cartera (CDC) pasan a reconstruirse a cierre
  de cada semana con pedidos y albaranes, en vez de depender de la foto diaria
  del panel (que no existía en muchas semanas y se hacía en días distintos).
  Se borran las filas reconstruidas antiguas de esos KPIs y se rehacen todas
  con el mismo criterio. Las semanas cerradas en vivo no se tocan.
· El WIP de una semana sin actividad de taller hereda la última foto.
· Se rellenan los huecos de las demás semanas y se regeneran las series.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        DELETE FROM apunts_kpi_serie WHERE clave IN ('cartera_pendiente', 'cdc', 'wip_valor');
        DELETE FROM apunts_kpi_semana
         WHERE clave IN ('cartera_pendiente', 'cdc', 'wip_valor') AND reconstruido = TRUE""")
    n = env["apunts.kpi.motor"].reconstruir_historico()
    _logger.info("KPIs Dirección: histórico rehecho para comparar semanas (%s valores)", n)
