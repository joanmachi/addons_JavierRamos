"""Los % por bloque del P&G llegaron vacíos a los registros ya abiertos antes
de la actualización: se recalculan todos para que no salgan a 0."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    recs = env["lira.pnl.period"].search([])
    for rec in recs:
        try:
            rec._compute_kpis_only()
        except Exception as e:  # noqa: BLE001
            _logger.warning("P&G %s: no se pudo recalcular (%s)", rec.id, e)
    _logger.info("P&G por Periodos: %d registros recalculados", len(recs))
