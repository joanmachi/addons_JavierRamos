"""Al actualizar: cerrar las fases que ya estaban validadas al 100 %.

El automatismo nuevo cierra la fase cuando el responsable valida la última
pieza, pero las fases que se validaron ANTES de esta versión quedaron
"en progreso" para siempre. Esto las repasa una a una y cierra las que tienen
todas las piezas de su orden validadas y nada pendiente."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    WO = env["mrp.workorder"]
    candidatas = WO.search([
        ("state", "not in", ("done", "cancel")),
        ("production_id.state", "not in", ("done", "cancel")),
        ("qty_validated", ">", 0),
    ])
    cerradas = 0
    for wo in candidatas:
        antes = wo.state
        try:
            wo._apunts_cerrar_si_validada()
            if wo.state == "done" and antes != "done":
                cerradas += 1
        except Exception as e:
            _logger.warning("No se pudo cerrar la fase %s (%s): %s", wo.id, wo.name, e)
    _logger.info("Validación de piezas: %s fase(s) atascadas cerradas.", cerradas)
