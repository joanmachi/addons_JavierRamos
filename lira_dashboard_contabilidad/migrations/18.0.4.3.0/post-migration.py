"""Pendientes de entrega: la tabla de detalle se guarda por usuario al pulsar
«Ver tabla». Tras cambiar el cálculo, las tablas ya generadas se quedaban con
los números viejos si se volvía a ellas por el historial del navegador. Se
regeneran todas con el cálculo nuevo."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT DISTINCT user_id FROM lira_pending_delivery_line WHERE user_id IS NOT NULL")
    usuarios = [r[0] for r in cr.fetchall()]
    for uid in usuarios:
        try:
            wiz = env["lira.pending.delivery"].with_user(uid).sudo().create({})
            wiz._compute_and_store()
        except Exception as e:  # noqa: BLE001
            _logger.warning("Pendientes de entrega: no se pudo regenerar la tabla del usuario %s (%s)", uid, e)
    _logger.info("Pendientes de entrega: tablas regeneradas para %d usuarios", len(usuarios))
