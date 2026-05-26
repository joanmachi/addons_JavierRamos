# -*- coding: utf-8 -*-
import logging
from odoo.http import request
from odoo.addons.stock_barcode_mrp.controllers.stock_barcode import MRPStockBarcode

_logger = logging.getLogger(__name__)

ACTIVE_STATES = ("confirmed", "progress", "to_close")


class ApuntsJrLotesBarcode(MRPStockBarcode):
    """
    Override para JAVIERRAMOS: redirige el escaneo nativo de la pantalla
    stock_barcode desde una OF cerrada (o renombrada con sufijo -001) a su
    última back-order activa.

    Caso típico: el cliente imprime el PDF cuando la OF se llama FAB/MO/00578.
    Al crear back-order, Odoo renombra la madre a FAB/MO/00578-001 y crea
    FAB/MO/00578-002 activa. El barcode FAB/MO/00578 original deja de
    matchear. Aquí lo resolvemos buscando primero match exacto y, si no, por
    prefijo + sufijo -NNN.
    """

    def _resolver_of_por_barcode(self, barcode):
        Production = request.env['mrp.production']

        # 1) Match exacto
        production = Production.search([('name', '=', barcode)], limit=1)
        if production:
            return production

        # 2) Match por prefijo: el PDF imprimió el nombre original FAB/MO/00578
        #    pero Odoo renombró la madre a FAB/MO/00578-001 al hacer backorder.
        candidatas = Production.search(
            [('name', '=like', barcode + '-%')], order='id asc',
        )
        # Filtramos para que el sufijo sea sólo dígitos (back-orders), no
        # interferir con otros patrones de nombre.
        def _es_backorder(name):
            sufijo = name[len(barcode) + 1:]
            return sufijo.isdigit()

        candidatas = candidatas.filtered(lambda p: _es_backorder(p.name))
        if not candidatas:
            return Production

        # Devolvemos la primera de la cadena (madre real, sufijo -001) para que
        # _apunts_get_ultima_activa() la use luego.
        return candidatas[0]

    def _try_open_production(self, barcode):
        production = self._resolver_of_por_barcode(barcode)
        if not production:
            return False

        # OF activa: comportamiento estándar
        if production.state in ACTIVE_STATES:
            return {'action': production.action_open_barcode_client_action()}

        # OF cerrada: buscar la última back-order activa de la cadena
        ultima_activa = production._apunts_get_ultima_activa()
        if ultima_activa and ultima_activa.id != production.id:
            _logger.info(
                "apunts_jr_parciales_of: scan nativo %s → OF cerrada %s, "
                "redirigiendo a back-order activa %s",
                barcode, production.name, ultima_activa.name,
            )
            return {'action': ultima_activa.action_open_barcode_client_action()}

        # Sin back-order activa: abrir la OF tal cual (idéntico a Enterprise)
        return {'action': production.action_open_barcode_client_action()}
