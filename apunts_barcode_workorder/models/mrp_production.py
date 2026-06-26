from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

import logging


_logger = logging.getLogger(__name__)


# Clave de contexto que usamos para evitar reentrancia. Cuando estamos dentro
# del flujo de auto-back-order ya disparado, NO queremos que la creacion de la
# back-order (que puede acabar tocando qty_validated via writes internos)
# vuelva a re-disparar el mismo flujo.
APUNTS_AUTO_BACKORDER_CTX = 'apunts_skip_auto_backorder'


class ManufacturingOrder(models.Model):
    _inherit = 'mrp.production'


    def comprobar_disponibilidad(self):

        self.action_assign()
        raw_states = self.move_raw_ids.mapped('state')
        if raw_states and all(s in ('done', 'cancel') for s in raw_states):
            return {
                'error': False,
                'mensaje': 'Materiales ya consumidos (OF reabierta)'
            }
        if self.reservation_state == 'assigned':
            return {
                'error': False,
                'mensaje': 'Componentes asignados'
            }
        if self.components_availability_state in ('late', 'unavailable', 'expected'):
            return {
                'error': True,
                'mensaje': 'No hay componentes'
            }
        return {
            'error': True,
            'mensaje': 'Componentes parcialmente disponibles (estado: %s)' % (self.reservation_state or 'desconocido')
        }
    def iniciar_parar_orden(self, barcode, empleado):
        orden = self.env['mrp.workorder'].search([('barcode', '=', barcode)], limit = 1)
        for orden in self.workorder_ids:
            raw_states = orden.production_id.move_raw_ids.mapped('state')
            materiales_consumidos = raw_states and all(s in ('done', 'cancel') for s in raw_states)
            if not materiales_consumidos and orden.production_id.reservation_state != 'assigned' and orden.production_id.components_availability_state in ('late', 'unavailable', 'expected'):
                return {
                    'error': True,
                    'mensaje': 'No hay componentes'
                }
            if orden.barcode == barcode:
                es_conjunto = orden.production_id.product_id.product_tmpl_id.tipo_producto == 'conjunto'
                if not es_conjunto and orden.prev_validated_qty == 0:
                    return {
                        'error': True,
                        'mensaje': 'La orden no tiene cantidad a producir'
                    }
                orden_iniciada = False
               
                if empleado['id'] in orden.employee_ids.ids:
                    orden_iniciada = True

                if not orden_iniciada:
                    orden.start_employee(employee_id = empleado['id'])
                    return {
                        'error': False,
                        'mensaje': 'Iniciado correctamente'
                    }
                else:
                    # No se desficha por esta vía (p. ej. reescaneo de la OF):
                    # el desfichaje obliga a registrar las piezas realizadas.
                    # Se hace desde el botón PAUSAR, que abre el diálogo de
                    # cantidad y, al confirmar, finaliza el fichaje.
                    return {
                        'error': True,
                        'mensaje': 'Para desficharte de esta fase usa el botón PAUSAR y registra las piezas realizadas.'
                    }

        return {
            'error': True,
            'mensaje': 'No se pudo iniciar la orden'
        }

    def _get_stock_barcode_data(self):
        data = super()._get_stock_barcode_data()
        ordenes = self.workorder_ids.sorted('sequence')

        data['log_note'] = self.log_note
        data['workorders'] = ordenes.read(ordenes._get_fields_stock_barcode(), load=False)
        data['product_image'] = self.product_id.image_256
        data['product_name'] = self.product_id.display_name
        data['product_docs'] = [
            {
                'id': att.id,
                'name': att.name,
                'url': '/web/content/%s?download=false' % att.id,
            }
            for att in self.product_id.product_tmpl_id.sudo().apunts_docs_taller_ids
        ]
        data['qty_produced'] = int(round(self.qty_produced or 0))
        data['product_qty'] = int(round(self.product_qty or 0))
        data['product_uom_name'] = self.product_uom_id.name or ''
        for wo_data in data['workorders']:
            wo_record = self.env['mrp.workorder'].browse(wo_data['id'])
            wo_data['prev_validated_qty'] = wo_record.prev_validated_qty
            wo_data['workcenter_name'] = wo_record.workcenter_id.display_name or ''
            mins = int(round(wo_record.duration_expected or 0))
            if mins >= 60:
                h, m = divmod(mins, 60)
                wo_data['duration_str'] = f"{h}h {m:02d}m" if m else f"{h}h"
            elif mins > 0:
                wo_data['duration_str'] = f"{mins}m"
            else:
                wo_data['duration_str'] = ''
        return data

    def enviar_notificacion(self, cantidad, trabajador, nombre_orden):
        if self.user_id:
            """
            self.message_post(
                body=f"El {trabajador['name']} a cambiado la cantidad a validar. Nueva cantidad: {cantidad}",
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[self.user_id.partner_id.id]
                )
            """
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary="Orden de trabajo actualizada",
                note=f"El operario {trabajador['name']} a actualizado la cantidad de la orden {nombre_orden}({self.name}). Nueva cantidad: {cantidad}."
            )
    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + ['log_note']

    def get_componentes_barcode(self):
        componentes = []
        for move in self.move_raw_ids.filtered(lambda m: m.state != 'cancel'):
            componentes.append({
                'id':           move.id,
                'nombre':       move.product_id.display_name,
                'referencia':   move.product_id.default_code or '',
                'cantidad':     move.product_uom_qty,
                'hecho':        move.quantity,
                'uom':          move.product_uom.name,
                'estado':       move.state,
            })
        return componentes

    # ------------------------------------------------------------------
    # Auto-producir + auto-back-order al validar piezas en la ultima fase
    # (apunts_barcode_workorder >= 18.0.1.0.4)
    # ------------------------------------------------------------------

    def _apunts_es_ultima_fase(self, workorder):
        """Devuelve True si `workorder` es la ultima fase de esta produccion.

        Criterio:
        - Si hay una sola WO -> esa es la ultima.
        - Si hay varias -> la de mayor `sequence` y, ante empate, la de mayor `id`.
        - Si `tipo_producto = 'conjunto'` y no hay sequence diferenciado,
          tambien la de mayor id (todas son "ultima" funcionalmente, pero
          para el trigger nos quedamos con una sola).
        """
        self.ensure_one()
        wos = self.workorder_ids
        if not wos or workorder not in wos:
            return False
        if len(wos) == 1:
            return True
        # ordenar por (sequence, id) ascendente -> ultima = mayor (seq, id)
        ultima = wos.sorted(key=lambda w: (w.sequence, w.id))[-1]
        return ultima.id == workorder.id

    def _apunts_snapshot_workorders(self):
        """Devuelve dict {clave: {'qty_validated', 'qty_ready_to_validate', 'operation_id', 'name', 'sequence'}}
        indexado por una clave estable que se mantiene al copiar a back-order.

        Clave preferida: operation_id (cada operacion del routing tiene id unico
        y se copia tal cual a la back-order). Fallback: (sequence, name).
        """
        self.ensure_one()
        snap = {}
        for wo in self.workorder_ids:
            key = self._apunts_wo_match_key(wo)
            snap[key] = {
                'qty_validated': wo.qty_validated or 0.0,
                'qty_ready_to_validate': wo.qty_ready_to_validate or 0.0,
                'operation_id': wo.operation_id.id if wo.operation_id else False,
                'name': wo.name,
                'sequence': wo.sequence,
            }
        return snap

    @staticmethod
    def _apunts_wo_match_key(workorder):
        """Clave para emparejar madre <-> back-order. operation_id si existe,
        si no fallback a (sequence, name)."""
        if workorder.operation_id:
            return ('op', workorder.operation_id.id)
        return ('seq', workorder.sequence, workorder.name)

    def _apunts_localizar_backorder(self):
        """Devuelve la back-order recien creada de esta cadena.

        La ultima MO de la cadena (mismo procurement_group) que NO sea esta
        y que aun no este cerrada/cancelada.
        """
        self.ensure_one()
        if not self.procurement_group_id:
            return self.env['mrp.production']
        candidatas = self.procurement_group_id.mrp_production_ids.filtered(
            lambda p: p.id != self.id and p.state in ('confirmed', 'progress', 'to_close')
        )
        if not candidatas:
            return self.env['mrp.production']
        # la mas reciente -> mayor backorder_sequence (o mayor id si empata)
        return candidatas.sorted(key=lambda p: (p.backorder_sequence, p.id))[-1]

    def _apunts_transferir_excedente_backorder(self, backorder, snapshot):
        """Para cada workorder de la back-order, busca su homologo en `snapshot`
        y le transfiere el excedente de qty_validated / qty_ready_to_validate
        que NO se ha producido en la madre.

        excedente_validated   = snapshot.qty_validated   - madre_producida
        excedente_ready       = snapshot.qty_ready - madre_producida_ready
        (en la practica madre_producida_ready=0 porque la madre ya cerro)

        Cap a backorder.product_qty.
        """
        self.ensure_one()
        if not backorder:
            return
        madre_producida = self.qty_producing or self.product_qty or 0.0
        for bo_wo in backorder.workorder_ids:
            key = self._apunts_wo_match_key(bo_wo)
            datos = snapshot.get(key)
            if not datos:
                # No hay homologo (no deberia pasar si la BoM no cambio). Log y skip.
                _logger.warning(
                    "[apunts_auto_backorder] WO back-order %s sin homologo en snapshot (key=%s)",
                    bo_wo.id, key,
                )
                continue
            cap = backorder.product_qty or 0.0
            excedente_val = max(0.0, (datos['qty_validated'] or 0.0) - madre_producida)
            excedente_ready = max(0.0, (datos['qty_ready_to_validate'] or 0.0) - madre_producida)
            # cap por seguridad
            excedente_val = min(excedente_val, cap)
            excedente_ready = min(excedente_ready, cap)
            vals = {}
            if not float_is_zero(excedente_val, precision_digits=6):
                vals['qty_validated'] = excedente_val
            if not float_is_zero(excedente_ready, precision_digits=6):
                vals['qty_ready_to_validate'] = excedente_ready
            if vals:
                bo_wo.with_context(**{APUNTS_AUTO_BACKORDER_CTX: True}).write(vals)
                _logger.info(
                    "[apunts_auto_backorder] WO back-order %s (%s) <- %s",
                    bo_wo.id, bo_wo.name, vals,
                )

    def _apunts_reficher_en_backorder(self, backorder, fichados_por_clave):
        """Re-ficha en el back-order los empleados que estaban fichados en la OF madre.

        Cuando cerramos la OF (button_mark_done), los fichajes abiertos se cierran.
        Si hay backorder, recreamos el fichaje en la fase equivalente para que el
        operario pueda seguir trabajando o al menos cerrar su jornada correctamente.
        """
        self.ensure_one()
        for bo_wo in backorder.workorder_ids:
            clave = self._apunts_wo_match_key(bo_wo)
            emp_ids = fichados_por_clave.get(clave, [])
            for emp_id in emp_ids:
                try:
                    bo_wo.with_context(**{APUNTS_AUTO_BACKORDER_CTX: True}).start_employee(
                        employee_id=emp_id
                    )
                    _logger.info(
                        "[apunts_auto_backorder] Empleado %s re-fichado en WO %s (%s) del back-order %s",
                        emp_id, bo_wo.id, bo_wo.name, backorder.name,
                    )
                except Exception:
                    _logger.warning(
                        "[apunts_auto_backorder] No se pudo re-fichar empleado %s en WO %s del back-order %s",
                        emp_id, bo_wo.id, backorder.name,
                        exc_info=True,
                    )

    def _apunts_resolver_cadena_wizards(self, action, max_loops=5):
        """Sigue la cadena de wizards lanzados por button_mark_done hasta que
        la accion sea None (cierre completado) o se exceda el limite.

        Maneja:
        - `mrp.consumption.warning`: lo confirma silenciosamente (equivale al
          boton "Continuar" del usuario tras ver el aviso de consumo).
        - `mrp.production.backorder`: lo confirma con `action_backorder`,
          forzando la creacion de la back-order para esta MO.

        Cualquier otra accion devuelta se retorna sin tocar.
        """
        for _ in range(max_loops):
            if not action or not isinstance(action, dict):
                return action
            res_model = action.get('res_model')
            ctx = dict(action.get('context') or {})
            ctx[APUNTS_AUTO_BACKORDER_CTX] = True
            if res_model == 'mrp.consumption.warning':
                line_vals = ctx.pop('default_mrp_consumption_warning_line_ids', [])
                mrp_ids = ctx.pop('default_mrp_production_ids', [])
                wizard = self.env['mrp.consumption.warning'].with_context(ctx).create({
                    'mrp_production_ids': [(6, 0, mrp_ids)] if mrp_ids else [],
                    'mrp_consumption_warning_line_ids': line_vals,
                })
                _logger.info(
                    "[apunts_auto_backorder] Resolviendo consumption.warning para OF %s (skip_consumption)",
                    self.name,
                )
                action = wizard.action_confirm()
                continue
            if res_model == 'mrp.production.backorder':
                line_vals = ctx.pop('default_mrp_production_backorder_line_ids', [])
                mrp_ids = ctx.pop('default_mrp_production_ids', [])
                wizard = self.env['mrp.production.backorder'].with_context(ctx).create({
                    'mrp_production_ids': [(6, 0, mrp_ids)] if mrp_ids else [],
                    'mrp_production_backorder_line_ids': line_vals,
                })
                # Forzar que la linea de ESTA MO se marque para backorder.
                for line in wizard.mrp_production_backorder_line_ids:
                    if line.mrp_production_id.id == self.id:
                        line.to_backorder = True
                _logger.info(
                    "[apunts_auto_backorder] Resolviendo production.backorder para OF %s",
                    self.name,
                )
                action = wizard.action_backorder()
                continue
            # mrp.production es la accion estandar de Odoo tras cerrar y crear
            # back-order: devuelve la ventana de la MO original. Es el final
            # natural de la cadena, no un error.
            if res_model != 'mrp.production':
                _logger.warning(
                    "[apunts_auto_backorder] Accion no reconocida en cadena: model=%s",
                    res_model,
                )
            return action
        _logger.warning(
            "[apunts_auto_backorder] OF %s: cadena de wizards excedio max_loops=%s",
            self.name, max_loops,
        )
        return action

    def _apunts_auto_producir_y_backorder(self, qty_validada_ultima_fase):
        """Cierra la produccion automaticamente, creando back-order si procede,
        y transfiere el excedente de las fases previas a la back-order.

        `qty_validada_ultima_fase`: cantidad validada (acumulada) en la ultima
        fase TRAS el ultimo incremento. Define qty_producing de la madre.
        """
        self.ensure_one()
        if self.state not in ('confirmed', 'progress', 'to_close'):
            _logger.info(
                "[apunts_auto_backorder] OF %s en estado %s, no se auto-cierra",
                self.name, self.state,
            )
            return
        if float_is_zero(qty_validada_ultima_fase, precision_digits=6):
            return

        # Guard: si la OF tiene mas de un finished_move activo, abortar.
        # Eso indica estado corrupto (sintoma del bug ensure_one en _cal_price).
        # Continuar provocaria mas zombies en stock_move.
        finished_activos = self.move_finished_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.product_id == self.product_id
        )
        if len(finished_activos) > 1:
            _logger.warning(
                "[apunts_auto_backorder] OF %s tiene %s finished_moves activos para el "
                "producto principal (esperado 1). Skip auto-cierre - estado corrupto. IDs=%s",
                self.name, len(finished_activos), finished_activos.ids,
            )
            return

        rounding = self.product_uom_id.rounding or 0.01
        product_qty = self.product_qty or 0.0
        # cap: nunca producir mas de product_qty (seguridad)
        qty_a_producir = min(qty_validada_ultima_fase, product_qty)

        # snapshot ANTES de tocar nada
        snapshot = self._apunts_snapshot_workorders()
        _logger.info(
            "[apunts_auto_backorder] OF %s: qty_validada_ultima_fase=%s, product_qty=%s, snapshot=%s",
            self.name, qty_validada_ultima_fase, product_qty, snapshot,
        )

        # Set qty_producing
        self.with_context(**{APUNTS_AUTO_BACKORDER_CTX: True}).write({
            'qty_producing': qty_a_producir,
        })

        # Limpiar move_lines previas del finished move del producto principal.
        # El JS de la pantalla taller (stock_barcode_mrp/save_barcode_data) crea
        # una move_line al validar piezas en taller; button_mark_done crea otra
        # en _post_inventory con quantity=qty_producing. El campo `quantity` del
        # stock.move es computed (suma move_lines) -> aparece quantity duplicada
        # (ej. "2/1" cuando product_qty=1 y qty_producing=1). Limpiando aqui
        # forzamos que solo quede la move_line que Odoo creara consistentemente.
        for move in self.move_finished_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.product_id == self.product_id
        ):
            if move.move_line_ids:
                move.move_line_ids.with_context(**{APUNTS_AUTO_BACKORDER_CTX: True}).unlink()

        # Capturar empleados fichados ANTES de que button_mark_done los cierre.
        # En nuestro flujo personalizado no podemos garantizar que Odoo llame
        # _stop_all_employees correctamente (depende de _do_finish en cada WO).
        # Los cerramos explícitamente aquí para que no queden fichajes huérfanos,
        # y guardamos los ids para re-ficharlos en el back-order después.
        now = fields.Datetime.now()
        fichados_por_clave = {}
        for wo in self.workorder_ids:
            open_times = wo.time_ids.filtered(lambda t: not t.date_end)
            if not open_times:
                continue
            clave = self._apunts_wo_match_key(wo)
            fichados_por_clave[clave] = open_times.mapped('employee_id').ids
            # Cerrar explícitamente el registro de productividad y desfichar
            open_times.write({'date_end': now})
            wo.with_context(**{APUNTS_AUTO_BACKORDER_CTX: True}).write(
                {'employee_ids': [(5,)]}
            )
            _logger.info(
                "[apunts_auto_backorder] OF %s WO %s: cerrados %d fichajes abiertos antes de cerrar",
                self.name, wo.name, len(open_times),
            )

        # Decidir cierre con o sin back-order
        cmp = float_compare(qty_a_producir, product_qty, precision_rounding=rounding)
        ctx_base = {APUNTS_AUTO_BACKORDER_CTX: True}
        try:
            with self.env.cr.savepoint():
                if cmp >= 0:
                    # Cierre completo, sin back-order
                    action = self.with_context(**ctx_base).button_mark_done()
                    action = self._apunts_resolver_cadena_wizards(action)
                    _logger.info(
                        "[apunts_auto_backorder] OF %s cerrada completa (cmp=%s, final_action=%s)",
                        self.name, cmp, action,
                    )
                else:
                    # Cierre parcial -> forzar back-order
                    action = self.with_context(**ctx_base).button_mark_done()
                    action = self._apunts_resolver_cadena_wizards(action)
                    _logger.info(
                        "[apunts_auto_backorder] OF %s cerrada con back-order (cmp=%s, final_action=%s)",
                        self.name, cmp, action,
                    )
                    # Localizar y transferir excedente
                    backorder = self._apunts_localizar_backorder()
                    if backorder:
                        self._apunts_transferir_excedente_backorder(backorder, snapshot)
                        # Re-fichar en el back-order a los operarios que estaban
                        # trabajando en la OF madre para que puedan seguir.
                        if fichados_por_clave:
                            self._apunts_reficher_en_backorder(backorder, fichados_por_clave)
                        _logger.info(
                            "[apunts_auto_backorder] Back-order generada: %s (id=%s, qty=%s)",
                            backorder.name, backorder.id, backorder.product_qty,
                        )
                    else:
                        _logger.warning(
                            "[apunts_auto_backorder] OF %s: no se localizo back-order tras button_mark_done",
                            self.name,
                        )
        except UserError as e:
            _logger.error(
                "[apunts_auto_backorder] OF %s: UserError en button_mark_done -> rollback. %s",
                self.name, e,
            )
            # Re-raise: que el operario lo vea en pantalla. El savepoint ya
            # deshizo el qty_producing escrito antes.
            raise
        except Exception as e:
            _logger.exception(
                "[apunts_auto_backorder] OF %s: excepcion inesperada -> rollback",
                self.name,
            )
            raise