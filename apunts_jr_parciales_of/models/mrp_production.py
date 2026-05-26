# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ACTIVE_STATES = ("confirmed", "progress", "to_close")
CLOSED_STATES = ("done", "cancel")


class MrpProductionLotesOf(models.Model):
    _inherit = "mrp.production"

    # ------------------------------------------------------------------
    # Campo auxiliar: índice de lote dentro de la cadena (1 = madre)
    # ------------------------------------------------------------------
    apunts_lote_index = fields.Integer(
        string="N. Lote",
        compute="_compute_apunts_lote_index",
        store=False,
    )

    @api.depends("name", "procurement_group_id")
    def _compute_apunts_lote_index(self):
        for prod in self:
            name = prod.name or ""
            # La madre no lleva sufijo (-001, -002…).
            # Los back-orders llevan "-NNN" al final.
            if "-" in name.split("/")[-1]:
                try:
                    suffix = name.rsplit("-", 1)[-1]
                    prod.apunts_lote_index = int(suffix) + 1
                except ValueError:
                    prod.apunts_lote_index = 1
            else:
                prod.apunts_lote_index = 1

    # ------------------------------------------------------------------
    # Helpers: cadena de OFs (madre + back-orders)
    # ------------------------------------------------------------------
    def _apunts_get_cadena(self):
        """
        Devuelve todas las mrp.production de la misma cadena,
        ordenadas cronológicamente (madre primero, back-orders después).

        Estrategia:
          1. Buscar la madre: la OF de la cadena sin sufijo numérico.
             Si self ES la madre, la tomamos directamente.
          2. Usar procurement_group_id para buscar todas las OFs del grupo.
          3. Ordenar por id (las madres se crean antes que sus back-orders).

        Caso sin procurement_group (OF suelta, sin SO vinculado):
          Solo se devuelve self — no hay back-orders que enlazar.
        """
        self.ensure_one()
        if not self.procurement_group_id:
            return self

        cadena = self.search(
            [("procurement_group_id", "=", self.procurement_group_id.id)],
            order="id asc",
        )
        return cadena

    def _apunts_get_ultima_activa(self):
        """
        Dado self (cualquier OF de la cadena), devuelve la última back-order
        activa. Si ninguna está activa, devuelve la madre (última de la cadena).
        """
        self.ensure_one()
        cadena = self._apunts_get_cadena()
        activas = cadena.filtered(lambda p: p.state in ACTIVE_STATES)
        if activas:
            # La última activa = la de id más alto (creada más tarde)
            return activas.sorted("id")[-1]
        # Todas cerradas: devolver la de mayor id (última de la cadena)
        return cadena.sorted("id")[-1]

    # ------------------------------------------------------------------
    # Override de iniciar_parar_orden — barcode persistente
    # ------------------------------------------------------------------
    def iniciar_parar_orden(self, barcode, empleado):
        """
        Override del método de apunts_barcode_workorder.

        Añade lógica de redirección de barcode madre → back-order activa:
          - Si el barcode escaneado corresponde a una OF diferente de self
            (el operario tiene impreso el PDF de la madre pero está viendo
            una back-order, o viceversa), se busca la OF por nombre.
          - Si esa OF está cerrada y tiene back-orders activas, se redirige
            a la última back-order activa.
          - Si la OF escaneada ES self (caso normal), se deja pasar al super.
        """
        # 1. Buscar la OF por el barcode/nombre escaneado
        of_escaneada = self.search([("name", "=", barcode)], limit=1)

        if not of_escaneada:
            # No es un nombre de OF — puede ser un barcode de workorder.
            # Delegamos al método padre sin modificar.
            return super().iniciar_parar_orden(barcode, empleado)

        # 2. Si la OF escaneada está cerrada, buscar la back-order activa
        if of_escaneada.state in CLOSED_STATES:
            of_activa = of_escaneada._apunts_get_ultima_activa()
            if of_activa.id != of_escaneada.id:
                _logger.info(
                    "apunts_jr_parciales_of: barcode %s → OF cerrada %s, "
                    "redirigiendo a back-order activa %s",
                    barcode,
                    of_escaneada.name,
                    of_activa.name,
                )
                # Llamar iniciar_parar_orden en la OF activa con el barcode
                # de la madre (el barcode del workorder coincide con el nombre
                # de la OF — apunts_barcode_workorder usa el campo barcode del
                # workorder, que coincide con el nombre de la producción).
                # Pasamos el barcode original porque los workorders de la OF
                # activa tienen su propio barcode (nombre de la OF activa).
                # Necesitamos el barcode del workorder de la OF activa.
                return of_activa._iniciar_parar_orden_por_of(empleado)

        # 3. Si la OF escaneada coincide con self o está activa, llamar al padre
        if of_escaneada.id != self.id:
            # El operario escaneó la OF madre estando en una back-order
            # (o al revés) pero la madre sigue activa — redirigir igualmente.
            if of_escaneada.state in ACTIVE_STATES:
                of_activa = of_escaneada._apunts_get_ultima_activa()
                if of_activa.id != self.id:
                    return of_activa._iniciar_parar_orden_por_of(empleado)

        return super().iniciar_parar_orden(barcode, empleado)

    def _iniciar_parar_orden_por_of(self, empleado):
        """
        Inicia/para el primer workorder activo de self para el empleado dado.
        Equivale a llamar iniciar_parar_orden con el barcode del primer
        workorder de self.
        """
        self.ensure_one()
        for orden in self.workorder_ids:
            if orden.state not in ("done", "cancel"):
                # Reutilizar la lógica del padre usando el barcode del workorder
                return super(MrpProductionLotesOf, self).iniciar_parar_orden(
                    orden.barcode, empleado
                )
        return {
            "error": True,
            "mensaje": "No hay operaciones activas en la OF %s" % self.name,
        }

    # ------------------------------------------------------------------
    # Campo Many2many computado para la pestaña Lotes (solo en vista)
    # Many2many computed sin store es válido para mostrar listas read-only
    # en Odoo 18 sin necesitar tabla intermedia real.
    # ------------------------------------------------------------------
    apunts_lotes_ids = fields.Many2many(
        comodel_name="mrp.production",
        relation="apunts_jr_parciales_of_cadena_rel",
        column1="production_id",
        column2="lote_id",
        compute="_compute_apunts_lotes_ids",
        string="Lotes de la cadena",
    )

    @api.depends("procurement_group_id")
    def _compute_apunts_lotes_ids(self):
        for prod in self:
            if prod.id and prod.procurement_group_id:
                cadena = self.search(
                    [("procurement_group_id", "=", prod.procurement_group_id.id)],
                    order="id asc",
                )
                prod.apunts_lotes_ids = cadena
            else:
                prod.apunts_lotes_ids = prod if prod.id else self.env["mrp.production"]
