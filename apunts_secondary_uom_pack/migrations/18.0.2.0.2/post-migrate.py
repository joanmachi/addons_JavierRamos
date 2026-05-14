"""Migración v18.0.2.0.2 — limpiar `secondary_uom_qty` heredado por
copy() en moves NO finalizados.

Hasta v18.0.2.0.1 el campo `stock.move.secondary_uom_qty` tenía `copy=True`
(default), de modo que en devoluciones, cambios de cantidad de OF y otras
duplicaciones, el valor del move original se propagaba al nuevo. Eso
generaba columnas "Cant. (sec.)" rellenas con números teóricos cuando la
"Cantidad" real estaba en 0 — confuso para el operario y peligroso si
validaba sin mirar.

Esta migración limpia esos arrastres SOLO en moves que aún no se han
ejecutado (state != 'done' y != 'cancel'). Los moves históricos no se
tocan — son datos contables/operativos cerrados.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE stock_move
        SET secondary_uom_qty = 0.0
        WHERE state NOT IN ('done', 'cancel')
          AND secondary_uom_qty IS NOT NULL
          AND secondary_uom_qty != 0
        """
    )
    affected = cr.rowcount
    if affected:
        _logger.info(
            "Apunts secondary_uom_pack v18.0.2.0.2: limpiados %s moves "
            "con secondary_uom_qty heredado de un copy() (state != done).",
            affected,
        )
    else:
        _logger.info(
            "Apunts secondary_uom_pack v18.0.2.0.2: no había moves con "
            "secondary_uom_qty residual."
        )
