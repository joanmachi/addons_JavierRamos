from datetime import timedelta

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.addons.resource.models.utils import Intervals, sum_intervals
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, format_datetime, float_is_zero, float_round
from odoo.http import request

import logging


_logger = logging.getLogger(__name__)


# Importamos la clave de contexto del otro modulo para mantenerlo en un solo sitio.
from .mrp_production import APUNTS_AUTO_BACKORDER_CTX


class WorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    qty_ready_to_validate = fields.Float(string="Cant. por validar", default=0.0, copy=False)
    qty_validated = fields.Float(string="Cant. validada", default=0.0, copy=False)
    # Piezas de esta fase pendientes de RECIBIR el material comprado para
    # reponerlas (refabricación): no tienen material físico todavía, así que NO
    # cuentan como "por hacer" ni se pueden validar hasta que llegue la compra.
    # Lo rellena/libera lira_mfg_supervisor (reposición). Aquí solo es el mecanismo.
    apunts_qty_pdte_recepcion = fields.Float(
        string="Pdte. recepción", default=0.0, copy=False,
        help="Piezas a reponer cuyo material comprado aún no se ha recibido. "
             "Bloqueadas para producir/validar hasta la recepción de la compra.")
    prev_validated_qty = fields.Float(
        string="Qty from Previous Stage", 
        compute="_compute_prev_validated_qty"
    )
    
    texto_fichados = fields.Char(
        string="Fichados", 
        compute="_compute_texto_fichados"
    )
    

    @api.depends('employee_ids')
    def _compute_texto_fichados(self):
        for wo in self:
            wo.texto_fichados = ', '.join(wo.employee_ids.mapped('name'))

    def _apunts_techo_validable(self, qty_validated=None):
        """Tope de piezas que esta fase puede tener 'por validar' (qty_ready_to_validate):
        es la capacidad de la fase menos lo ya validado.
          - 1ª fase / producto 'conjunto': capacidad = product_qty de la OF.
          - fases siguientes:              capacidad = uds validadas en la fase previa.
        `prev_validated_qty` ya es (capacidad - qty_validated), así que recuperamos la
        capacidad y restamos las uds validadas (las nuevas, si vienen en el write)."""
        self.ensure_one()
        val = self.qty_validated if qty_validated is None else qty_validated
        capacidad = (self.prev_validated_qty or 0.0) + (self.qty_validated or 0.0)
        # Las piezas pendientes de recibir material (reposición) NO se pueden
        # registrar todavía: se descuentan del tope.
        pdte = self.apunts_qty_pdte_recepcion or 0.0
        return max(capacidad - (val or 0.0) - pdte, 0.0)

    @api.depends('production_id.workorder_ids.qty_validated')
    def _compute_prev_validated_qty(self):
        for wo in self:
            all_wos = wo.production_id.workorder_ids.sorted('sequence')
            prev_wos = all_wos.filtered(lambda w: w.sequence < wo.sequence)
            es_conjunto = wo.production_id.product_id.product_tmpl_id.tipo_producto == 'conjunto'

            if es_conjunto or not prev_wos:
                wo.prev_validated_qty = wo.production_id.product_qty - wo.qty_validated
            else:
                wo.prev_validated_qty = prev_wos[-1].qty_validated - wo.qty_validated

  
    def _apunts_piezas_por_hacer(self):
        """Piezas que REALMENTE quedan por hacer en esta fase.

        Es el mismo número que la tablet enseña al operario como "Por hacer":
        de lo que le toca hacer se descuenta lo que ya entregó y está esperando
        el visto bueno del responsable, y lo que está pendiente de recibir
        material. Si sale 0, en esta fase no hay nada que fichar."""
        self.ensure_one()
        return max(
            (self.prev_validated_qty or 0.0)
            - (self.qty_ready_to_validate or 0.0)
            - (self.apunts_qty_pdte_recepcion or 0.0),
            0.0,
        )

    def _apunts_comprobar_puede_fichar(self):
        """No dejar fichar en una fase que ya no tiene trabajo.

        Antes se podía: el operario fichaba en una fase cuyas piezas estaban
        pendientes de validar, llegaba el responsable, validaba, y el fichaje
        se quedaba en el aire (o peor: al fichar, la orden volvía de "Por
        cerrar" a "En progreso" y deshacía la validación)."""
        self.ensure_one()
        if self.production_id.state in ("done", "cancel"):
            raise UserError(
                "La orden %s ya está %s: no se puede fichar en ella."
                % (self.production_id.name,
                   "terminada" if self.production_id.state == "done" else "cancelada")
            )
        if self.state in ("done", "cancel"):
            raise UserError(
                "La fase «%s» ya está terminada: no se puede fichar en ella.\n\n"
                "Si queda trabajo, avisa al responsable para que la reabra."
                % (self.name or "")
            )
        if self._apunts_piezas_por_hacer() <= 0:
            pendientes = self.qty_ready_to_validate or 0.0
            if pendientes > 0:
                raise UserError(
                    "En «%s» no queda ninguna pieza por hacer.\n\n"
                    "Las %s que hiciste están PENDIENTES DE VALIDAR por el "
                    "responsable. Ficha en otra fase o en otra orden."
                    % (self.name or "", int(pendientes) if float(pendientes).is_integer() else pendientes)
                )
            raise UserError(
                "En «%s» no queda ninguna pieza por hacer, así que no se puede "
                "fichar. Ficha en otra fase o en otra orden." % (self.name or "")
            )

    def _apunts_cerrar_si_validada(self):
        """Marca la fase como HECHA cuando David valida la última pieza.

        Antes, al validar todas las piezas de una fase intermedia, la fase se
        quedaba "en progreso" para siempre en fabricación y en los informes
        (solo la última fase de la orden tenía automatismo). Ahora, si ya no
        queda nada por hacer ni por validar, la fase se cierra sola: se
        desficha a quien siguiera dentro y pasa a verde.
        """
        for wo in self:
            if wo.state in ("done", "cancel"):
                continue
            # El listón es el TOTAL de piezas de la orden, no la capacidad del
            # momento: en una fase intermedia la capacidad crece cuando la fase
            # anterior valida más, y cerrarla antes de tiempo la dejaría
            # bloqueada para el trabajo que aún va a llegarle.
            total_of = wo.production_id.product_qty or 0.0
            if total_of <= 0:
                continue
            if float_compare(wo.qty_validated or 0.0, total_of, precision_digits=2) < 0:
                continue
            if float_compare(wo.qty_ready_to_validate or 0.0, 0.0, precision_digits=2) > 0:
                continue
            if float_compare(wo.apunts_qty_pdte_recepcion or 0.0, 0.0, precision_digits=2) > 0:
                continue  # hay refabricación en camino: la fase sigue viva
            # Cerrar los fichajes que siguieran abiertos en esta fase para no
            # dejarlos huérfanos (button_finish los remata con end_all).
            try:
                wo.end_all()
            except Exception:
                pass
            try:
                wo.button_finish()
                # La fase terminó de verdad cuando acabó el último fichaje, no
                # cuando el responsable validó: así los informes semanales la
                # cuentan en su semana y no en la del cierre.
                ultimo = max(wo.time_ids.filtered("date_end").mapped("date_end"), default=None)
                if ultimo and wo.date_finished and ultimo < wo.date_finished:
                    wo.write({"date_finished": ultimo})
                _logger.info(
                    "[apunts_validacion] Fase %s (%s) cerrada automáticamente: "
                    "todas las piezas validadas.", wo.id, wo.name)
            except Exception as e:
                _logger.warning(
                    "[apunts_validacion] No se pudo cerrar la fase %s (%s): %s",
                    wo.id, wo.name, e)

    def start_employee(self, employee_id):
        """Override para retrotraer el inicio del fichaje al último desfichaje del
        empleado cuando el tiempo transcurrido es menor que el umbral de inactividad.
        Así se elimina el tiempo muerto entre OF sin coste contable."""
        now = fields.Datetime.now()
        # Puerta única para barcode, Fabricación y Shop Floor: por aquí pasan
        # todas las formas de empezar a fichar. El re-fichaje automático del
        # back-order va exento (lo lanza el propio sistema al partir la orden).
        if not self.env.context.get(APUNTS_AUTO_BACKORDER_CTX):
            self._apunts_comprobar_puede_fichar()
        super().start_employee(employee_id)

        # No backdatear en el flujo de auto-back-order: el fichaje ya viene
        # correctamente desde el cierre de la OF madre.
        if self.env.context.get(APUNTS_AUTO_BACKORDER_CTX):
            return

        ICP = self.env['ir.config_parameter'].sudo()
        min_inact = int(
            ICP.get_param('apunts_taller_control.bloqueo_inactividad_min', '30')
        )
        if not min_inact:
            return

        # Último desfichaje de este empleado en cualquier WO
        ultima = self.env['mrp.workcenter.productivity'].search(
            [('employee_id', '=', employee_id), ('date_end', '!=', False)],
            order='date_end DESC',
            limit=1,
        )
        if not ultima or ultima.date_end < now - timedelta(minutes=min_inact):
            return

        # Ajustar date_start del registro recién creado al último date_end
        nueva = self.env['mrp.workcenter.productivity'].search(
            [
                ('employee_id', '=', employee_id),
                ('workorder_id', '=', self.id),
                ('date_end', '=', False),
            ],
            order='id DESC',
            limit=1,
        )
        if nueva:
            nueva.write({'date_start': ultima.date_end})

    def finalizar_fichaje(self,empleado, qty=0):
        if empleado and empleado['id']:
            for orden in self:
                #if (orden.qty_ready_to_validate) >= orden.prev_validated_qty:
                for empleado_id in orden.employee_ids:
                    if empleado['id'] == empleado_id.id:
                        if qty > 0:
                            for fichaje in orden.time_ids:
                                if fichaje.employee_id.id == empleado_id.id and (not fichaje.date_end):
                                    fichaje.write({
                                        'cantidad_introducida' : qty,
                                        'cantidad_total_actual' : orden.qty_ready_to_validate
                                    })
                                    break 
                        orden.stop_employee([empleado['id']])
    def action_open_qty_wizard(self):
        return {
            'name': 'Validar cantidades',
            'type': 'ir.actions.act_window',
            'res_model': 'workorder.qty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_new_qty': 0
            }
        }
    





    def _get_fields_stock_barcode(self):
        return [
            'id',
            'name',
            'barcode',
            'duration',
            'employee_id',
            'employee_ids',
            'employee_name',
            'working_user_ids',
            'qty_done',
            'qty_produced',
            'qty_producing',
            'qty_remaining',
            'qty_ready_to_validate',
            'qty_validated',
            'prev_validated_qty',
            'apunts_qty_pdte_recepcion',
            'texto_fichados',
        ]
    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        for wo_data in res.get('workorders', []):
            wo = self.browse(wo_data['id'])
            wo_data['prev_validated_qty'] = wo.prev_validated_qty
            wo_data['texto_fichados'] = wo.texto_fichados
        return res

    # ------------------------------------------------------------------
    # Auto-producir + auto-back-order: trigger en write de qty_validated
    # (apunts_barcode_workorder >= 18.0.1.0.4)
    # ------------------------------------------------------------------

    def write(self, vals):
        """Override para disparar `_apunts_auto_producir_y_backorder` cuando
        se incrementa `qty_validated` en la ULTIMA fase de una produccion.

        Casos en los que NO disparamos:
        - El contexto trae la flag `apunts_skip_auto_backorder` (reentrancia).
        - El write no toca `qty_validated`.
        - La WO no es la ultima fase de su produccion.
        - La produccion no esta en estado "abierto" (confirmed/progress/to_close).
        - Tras el write, qty_validated == 0 (no se ha avanzado nada).
        """
        # Blindaje (síncrono, antes de cualquier atajo): no se pueden registrar más
        # piezas 'por validar' de las pendientes de la fase. Evita que un operario
        # teclee por error un número enorme (p. ej. su código de empleado) como
        # cantidad. Se exime el flujo interno de back-order, que escribe con su
        # propio contexto y ya capa el excedente a la capacidad de la OF hija.
        if 'qty_ready_to_validate' in vals and not self.env.context.get(APUNTS_AUTO_BACKORDER_CTX):
            for wo in self:
                new_ready = vals.get('qty_ready_to_validate') or 0.0
                new_validated = vals.get('qty_validated', wo.qty_validated)
                techo = wo._apunts_techo_validable(new_validated)
                if float_compare(new_ready, techo, precision_digits=2) > 0:
                    raise ValidationError(_(
                        "No puedes registrar %(ready)s piezas en la fase «%(wo)s»: "
                        "solo quedan %(disp)s pendientes de realizar.",
                        ready=new_ready, wo=wo.name, disp=techo,
                    ))

        # Si no se toca qty_validated o estamos en el propio flujo, atajo.
        if 'qty_validated' not in vals or self.env.context.get(APUNTS_AUTO_BACKORDER_CTX):
            return super().write(vals)

        # Tomar snapshot de cambios antes para saber a quien disparar.
        wos_a_evaluar = []
        for wo in self:
            qty_prev = wo.qty_validated or 0.0
            qty_new = vals.get('qty_validated', qty_prev)
            if float_compare(qty_new, qty_prev, precision_digits=6) > 0:
                wos_a_evaluar.append(wo.id)

        res = super().write(vals)

        if not wos_a_evaluar:
            return res

        # Tras el write, disparar el auto-flujo en aquellas WOs que sean
        # ultima fase y cuya produccion siga abierta.
        for wo in self.browse(wos_a_evaluar):
            try:
                production = wo.production_id
                if not production or production.state not in ('confirmed', 'progress', 'to_close'):
                    continue
                if not production._apunts_es_ultima_fase(wo):
                    # Fase intermedia: si con esta validación queda al 100 %,
                    # se marca como hecha para que no siga saliendo pendiente.
                    wo._apunts_cerrar_si_validada()
                    continue
                if float_is_zero(wo.qty_validated or 0.0, precision_digits=6):
                    continue
                _logger.info(
                    "[apunts_auto_backorder] Trigger desde WO %s (%s), prod %s, qty_validated=%s",
                    wo.id, wo.name, production.name, wo.qty_validated,
                )
                production._apunts_auto_producir_y_backorder(wo.qty_validated)
            except UserError:
                # Propaga al usuario, ya logueado en _apunts_auto_producir_y_backorder
                raise
            except Exception:
                _logger.exception(
                    "[apunts_auto_backorder] Fallo no controlado en trigger WO %s",
                    wo.id,
                )
                raise

        return res
