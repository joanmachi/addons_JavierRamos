"""Tipo de stock: recalcular todo el catálogo porque la regla cambia (también
vale la referencia que va en el nombre), y arrastrar el cambio a los quants."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    P = env["product.template"].with_context(active_test=False)
    todos = P.search([])
    env.add_to_compute(P._fields["lira_tipo_stock"], todos)
    todos.flush_model()
    Q = env["stock.quant"]
    quants = Q.search([])
    env.add_to_compute(Q._fields["lira_tipo_stock"], quants)
    quants.flush_model()
    cr.execute("SELECT lira_tipo_stock, COUNT(*) FROM stock_quant WHERE quantity <> 0 GROUP BY 1")
    _logger.info("Tipo de stock recalculado: %s", dict(cr.fetchall()))
