"""Stock por cliente: rellena el cliente de todas las referencias existentes.

El campo es nuevo, así que la primera vez hay que recorrer el catálogo entero.
A partir de ahí lo mantiene el cron diario.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cambiadas = env["product.template"]._lira_asignar_cliente()
    con = env["product.template"].search_count([("lira_cliente_id", "!=", False)])
    _logger.info(
        "Stock por cliente: %d referencias asignadas (%d con cliente en total)",
        cambiadas, con,
    )
