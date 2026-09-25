import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Al instalar o actualizar, dejar los cuadros de mando ya con datos.

    Así el cliente no tiene que pulsar nada: la foto semanal se toma, y el
    registro semanal (CMI) y el de producción (CMP) se reconstruyen con lo que
    ya hay en la contabilidad, el almacén y los fichajes."""
    env["apunts.direccion.snapshot"].cron_tomar_foto()
    # Reunión semanal: catálogo de KPIs, pagos recurrentes del DAT e histórico
    try:
        env["apunts.kpi.bloque"]._sembrar()
        env["apunts.dat.pago"]._sembrar()
        n = env["apunts.kpi.motor"].reconstruir_historico()
        _logger.info("KPIs de Dirección: histórico reconstruido (%s valores).", n)
    except Exception as e:
        _logger.warning("KPIs de Dirección: no se pudo reconstruir el histórico: %s", e)
    for modelo, etiqueta in (("apunts.cmi.semana", "registro semanal (CMI)"),
                             ("apunts.cmp.mes", "producción (CMP)")):
        try:
            n = env[modelo].reconstruir_historico()
            _logger.info("Cuadro de mando: %s reconstruido (%s filas).", etiqueta, n)
        except Exception as e:  # que un fallo aquí no impida instalar el módulo
            _logger.warning("Cuadro de mando: no se pudo reconstruir %s: %s", etiqueta, e)
