"""Recalcular el tipo de stock (la categoría de consumibles manda) y volver a
asignar clientes, ahora también por el código que va en el nombre."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    P = env["product.template"].with_context(active_test=False)
    todos = P.search([])
    env.add_to_compute(P._fields["lira_tipo_stock"], todos)
    todos.flush_model()
    n = env["product.template"]._lira_asignar_cliente()
    Q = env["stock.quant"]
    quants = Q.search([])
    for f in ("lira_tipo_stock", "lira_cliente_id", "lira_vendido"):
        env.add_to_compute(Q._fields[f], quants)
    quants.flush_model()
    _logger.info("Stock: %d referencias con cliente nuevo tras leer el código del nombre", n)
