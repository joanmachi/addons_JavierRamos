import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recalcular los costes WIP de las OFs abiertas llamando al compute
    DIRECTAMENTE (add_to_compute + flush demostró no persistir en según
    qué orden de carga de módulos)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    mos = env["mrp.production"].search([("state", "not in", ("done", "cancel"))])
    mos._compute_apunts_wip_costs()
    env.flush_all()
    cr.commit()  # blindaje: en local el flush del post-migrate no persistió
    _logger.info("WIP: compute directo de costes en %s OFs abiertas.", len(mos))
