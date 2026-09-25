"""WIP: madres en curso, venta sin repetir en las hijas, cliente y fecha de entrega
heredados de la madre (CAMBIOS [061]).

Los campos nuevos (OF madre, criterio propio, fecha de entrega) los calcula Odoo
solo al crear la columna. Aquí se recalculan los que ya existían y cambian de
lógica: «en curso», venta y márgenes de las OF abiertas (el histórico de las OF
hechas no se toca) y el cliente de todas las OF no canceladas (solo informativo).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Mo = env["mrp.production"]
    abiertas = Mo.search([("state", "in", ("confirmed", "progress", "to_close"))])
    todas = Mo.search([("state", "!=", "cancel")])
    env.add_to_compute(Mo._fields["apunts_wip_propio"], abiertas)
    env.add_to_compute(Mo._fields["apunts_is_wip"], abiertas)
    env.add_to_compute(Mo._fields["apunts_sale_amount"], abiertas)
    env.add_to_compute(Mo._fields["apunts_partner_id"], todas)
    env.add_to_compute(Mo._fields["apunts_fecha_entrega"], todas)
    env.flush_all()
    # Los márgenes dependen de la venta: recalcularlos después, con la venta nueva.
    env.add_to_compute(Mo._fields["apunts_margen_of"], abiertas)
    env.flush_all()
    _logger.info(
        "WIP [061]: %s OF abiertas recalculadas; en curso ahora: %s; madres en curso: %s",
        len(abiertas),
        Mo.search_count([("apunts_is_wip", "=", True)]),
        Mo.search_count([("apunts_is_wip", "=", True), ("apunts_hija_ids", "!=", False)]),
    )
