"""Al actualizar: excluir del rendimiento por operario las fichas que no son
operarios reales (la empresa, los centros genéricos y los usuarios de prueba).
Sin esto, el ranking de rendimiento sale distorsionado y había que marcarlas
a mano en cada base."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

NO_OPERARIOS = ["Javier Ramos SL", "Planta", "Gestión", "Gestion",
                "ALEXAPUNTS", "juanfran", "JUANFRAN."]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    E = env["hr.employee"].with_context(active_test=False)
    marcados = 0
    for nombre in NO_OPERARIOS:
        for emp in E.search([("name", "=", nombre),
                             ("apunts_excluir_rendimiento", "=", False)]):
            emp.write({"apunts_excluir_rendimiento": True})
            marcados += 1
    _logger.info("Rendimiento por operario: %s ficha(s) genéricas excluidas.", marcados)
