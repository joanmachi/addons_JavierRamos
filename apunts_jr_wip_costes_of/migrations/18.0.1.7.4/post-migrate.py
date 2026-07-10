import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recalcular los costes WIP almacenados de las OFs abiertas tras el
    cambio de valoración (€/m por ratio real de la línea de compra).
    Sin esto, las tarjetas seguirían enseñando los importes viejos hasta
    que algún trigger las tocara."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Mo = env["mrp.production"]
    mos = Mo.search([("state", "not in", ("done", "cancel"))])
    campos = [
        f for f in ("apunts_mat_real_total", "apunts_mat_planned_total",
                    "apunts_cost_total_real", "apunts_cost_total_planned")
        if f in Mo._fields and Mo._fields[f].store
    ]
    for fname in campos:
        env.add_to_compute(Mo._fields[fname], mos)
    env.flush_all()
    _logger.info("WIP: recalculados %s campos de coste en %s OFs abiertas.", len(campos), len(mos))
