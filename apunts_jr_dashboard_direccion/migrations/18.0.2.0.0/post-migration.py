"""Al actualizar a 18.0.2.0.0, dejar los cuadros de mando ya con datos.

El post_init_hook del módulo solo corre al INSTALAR, así que en una base que ya
lo tenía instalado (la del cliente) los cuadros nuevos saldrían vacíos hasta que
alguien los recalculase. Esto los rellena solo, con lo que ya hay en la
contabilidad, el almacén y los fichajes."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for modelo, etiqueta in (("apunts.cmi.semana", "registro semanal (CMI)"),
                             ("apunts.cmp.mes", "producción (CMP)")):
        try:
            n = env[modelo].reconstruir_historico()
            _logger.info("Cuadro de mando: %s reconstruido (%s filas).", etiqueta, n)
        except Exception as e:
            _logger.warning("Cuadro de mando: no se pudo reconstruir %s: %s", etiqueta, e)
