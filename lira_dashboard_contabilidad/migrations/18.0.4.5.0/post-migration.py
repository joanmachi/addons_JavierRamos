"""Stock materia prima + precio de venta desde la última venta: recorre el
catálogo para marcar «con venta confirmada» y rellenar el PVP que falte."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    P = env["product.template"]
    sin_pvp_antes = P.search_count([("list_price", "=", 0), ("qty_available", ">", 0)])
    P._lira_asignar_cliente()
    sin_pvp = P.search_count([("list_price", "=", 0), ("qty_available", ">", 0)])
    _logger.info("Stock: referencias con stock y sin PVP %d → %d | con venta confirmada: %d",
                 sin_pvp_antes, sin_pvp, P.search_count([("lira_vendido", "=", True)]))
