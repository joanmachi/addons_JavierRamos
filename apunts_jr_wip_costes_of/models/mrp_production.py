import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _cal_price(self, consumed_moves):
        """Handle multiple finished moves from split productions.

        mrp_account._cal_price expects ensure_one() on the filtered finished_move,
        but when an MO has been split into parts, each split adds its own entry to
        move_finished_ids on the same production. The filter then returns N moves
        and ensure_one() raises ValueError. Catch and log rather than crashing
        the backorder — the backorder operation completes normally.
        """
        try:
            return super()._cal_price(consumed_moves)
        except ValueError as e:
            if 'Expected singleton' not in str(e):
                raise
            _logger.warning(
                "apunts._cal_price [%s]: multiple finished moves on split MO — "
                "standard price recalculation skipped, backorder continues. (%s)",
                self.name, e,
            )

    apunts_is_wip = fields.Boolean(
        string="En curso (WIP)",
        compute="_compute_apunts_wip_costs",
        store=True,
        index=True,
    )
    apunts_qty_pending = fields.Float(
        string="Pendiente",
        compute="_compute_apunts_wip_costs",
        store=True,
        help=(
            "Piezas que aún quedan por fabricar.\n"
            "\n"
            "FÓRMULA: Cantidad pedida − Hecho."
        ),
    )

    apunts_cost_total_planned = fields.Monetary(
        string="Coste teórico OF (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Lo que esta orden DEBERÍA costar según lo previsto.\n"
            "\n"
            "FÓRMULA: MP teórica + Coste operario teórico + Coste máquina teórico + Amortización teórica.\n"
            "\n"
            "Sale del routing del producto y de la lista de materiales (BoM). "
            "Si la BoM está incompleta, este valor sale más bajo de lo real."
        ),
    )
    apunts_cost_total_real = fields.Monetary(
        string="EN CURSO real (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Dinero ya COMPROMETIDO en esta orden hasta ahora mismo.\n"
            "\n"
            "FÓRMULA: MP real + Coste operario real + Coste máquina real + Amortización real.\n"
            "\n"
            "No incluye lo que aún queda por hacer. Es la foto del WIP a día de hoy."
        ),
    )
    apunts_mat_real_total = fields.Monetary(
        string="MP real (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Material que ya está COMPROMETIDO en esta orden.\n"
            "\n"
            "Para cada componente toma el MAYOR de estos dos:\n"
            "  • Importe ya recibido del proveedor (líneas de compra con "
            "campo 'Fabricación' = esta OF, multiplicado por la parte "
            "qty_recibida/qty_pedida).\n"
            "  • Importe ya consumido en taller (cantidad consumida × precio).\n"
            "\n"
            "El PRECIO se busca por cascada: línea de compra vinculada a "
            "esta OF → coste estándar del producto → último albarán de "
            "entrada con precio → media de compras anteriores → tarifa "
            "del proveedor."
        ),
    )
    apunts_mat_reposicion_extra = fields.Monetary(
        string="MP extra por reposición (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        copy=False,
        help=(
            "Material ADICIONAL por reponer piezas no validadas (desechadas y "
            "vueltas a fabricar) desde el panel de supervisor. Es el importe REAL "
            "de los pedidos de compra de reposición vinculados a la OF "
            "(líneas con 'Compra por reposición'), NO una estimación. Se SUMA al "
            "MP real y al coste total. El retrabajo NO suma aquí (solo mano de obra)."
        ),
    )
    apunts_mo_real_total = fields.Monetary(
        string="Coste operario real (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Dinero ya gastado en mano de obra (operario) en esta orden.\n"
            "\n"
            "FÓRMULA: SUMA por cada fichaje cerrado de [minutos fichados ÷ 60 × tarifa €/h del operario].\n"
            "\n"
            "Tarifa por cascada:\n"
            "  1) Coste/hora rellenado en ficha del empleado (RRHH).\n"
            "  2) Si el empleado está a 0, usa Coste/hora del empleado del centro de trabajo.\n"
            "\n"
            "Si las dos están a 0, sale 0."
        ),
    )
    apunts_machine_real_total = fields.Monetary(
        string="Coste máquina real (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Dinero ya gastado en uso de máquinas (centros de trabajo) en esta orden.\n"
            "\n"
            "FÓRMULA: SUMA por cada fichaje cerrado de [minutos fichados ÷ 60 × Coste/hora del centro].\n"
            "\n"
            "Si el centro tiene 'Coste por hora' a 0, sale 0."
        ),
    )
    apunts_mat_planned_total = fields.Monetary(
        string="MP teórica (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Lo que la materia prima de esta orden DEBERÍA costar según lo previsto.\n"
            "\n"
            "FÓRMULA: SUMA por cada componente del producto de [cantidad necesaria × precio].\n"
            "\n"
            "La cantidad necesaria sale de la lista de materiales (BoM) × cantidad a fabricar. "
            "El precio se busca por la misma cascada que la MP real.\n"
            "\n"
            "Si la BoM del producto está incompleta o tiene cantidades simbólicas, esta cifra "
            "sale más baja que la MP real (ver columna 'BoM incompleta')."
        ),
    )
    apunts_mo_planned_total = fields.Monetary(
        string="Coste operario teórico (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Lo que el operario DEBERÍA costar según los minutos previstos.\n"
            "\n"
            "FÓRMULA: SUMA por cada operación del producto de [minutos previstos ÷ 60 × tarifa €/h del operario].\n"
            "\n"
            "Tarifa por cascada:\n"
            "  1) Empleados asignados al workorder (si los hay).\n"
            "  2) Si no, Coste/hora del empleado del centro de trabajo."
        ),
    )
    apunts_machine_planned_total = fields.Monetary(
        string="Coste máquina teórico (€)",
        compute="_compute_apunts_wip_costs",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Lo que la máquina DEBERÍA costar según los minutos previstos.\n"
            "\n"
            "FÓRMULA: SUMA por cada operación del producto de [minutos previstos ÷ 60 × Coste/hora del centro de trabajo]."
        ),
    )
    apunts_bom_incompleta = fields.Boolean(
        string="BoM incompleta",
        compute="_compute_apunts_wip_costs",
        store=True,
        help=(
            "Aviso: la lista de materiales (BoM) del producto está mal configurada.\n"
            "\n"
            "Se marca cuando MP real > 1,5 × MP teórica Y MP real > 50 €.\n"
            "\n"
            "Causa típica en JR: falta algún componente en la BoM (servicio externo "
            "tipo mecanizado, pavonado, pintura) o tiene cantidades simbólicas (1u "
            "en lugar de la cantidad real). Conviene revisar la BoM del producto."
        ),
    )

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
    )

    apunts_of_short = fields.Char(
        string="OF",
        compute="_compute_apunts_of_short",
        store=True,
        help="Número corto de la OF (parte final tras la última /).",
    )
    apunts_qty_done = fields.Float(
        string="Hecho",
        compute="_compute_apunts_qty_done",
        store=True,
        help=(
            "Piezas ya fabricadas hasta ahora.\n"
            "\n"
            "Se toma el MAYOR de:\n"
            "  • Cantidad producida y validada en oficina.\n"
            "  • Cantidad marcada en taller pero aún sin validar parcial.\n"
            "\n"
            "En JR los operarios marcan la cantidad en taller, esa es la que cuenta."
        ),
    )

    @api.depends("qty_produced", "qty_producing")
    def _compute_apunts_qty_done(self):
        for prod in self:
            prod.apunts_qty_done = max(prod.qty_produced or 0.0, prod.qty_producing or 0.0)

    apunts_partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        compute="_compute_apunts_partner_id",
        store=True,
        help="Cliente del pedido de venta vinculado a la OF (vía sale_line/sale_id/procurement_group/x_studio_venta).",
    )
    apunts_margen_of = fields.Monetary(
        string="Margen OF (€)",
        compute="_compute_apunts_margen",
        store=True,
        currency_field="company_currency_id",
        help="Venta vinculada − Coste teórico total. Negativo = perdiendo dinero según previsto.",
    )
    apunts_margen_pct = fields.Float(
        string="Margen (%)",
        compute="_compute_apunts_margen",
        store=True,
        help="Margen € / Venta × 100. Calculado sobre coste TEÓRICO.",
    )
    apunts_margen_real_of = fields.Monetary(
        string="Margen real (€)",
        compute="_compute_apunts_margen",
        store=True,
        currency_field="company_currency_id",
        help="Venta vinculada − Coste REAL acumulado (lo fichado hasta el momento). "
             "Si el coste real es 0 (OF sin empezar) este margen es engañoso: ver columna "
             "'Margen real sin datos' / decoración roja.",
    )
    apunts_margen_real_pct = fields.Float(
        string="Margen real (%)",
        compute="_compute_apunts_margen",
        store=True,
        help="Margen real € / Venta × 100. Calculado sobre coste REAL acumulado.",
    )
    apunts_margen_real_dudoso = fields.Boolean(
        string="Margen real sin datos",
        compute="_compute_apunts_margen",
        store=True,
        help="True si el coste real es 0 (OF sin fichajes). El margen real entonces es "
             "100% artificial — usar decoración roja en vistas.",
    )
    apunts_factor_cobertura = fields.Float(
        string="Factor cobertura",
        compute="_compute_apunts_margen",
        store=True,
        digits=(6, 2),
        help="Venta / Coste real. Objetivo JR: ≥ 1,35. Valor < 1 = pérdidas.",
    )
    apunts_avance_coste_pct = fields.Float(
        string="Avance (coste) %",
        compute="_compute_apunts_margen",
        store=True,
        digits=(16, 1),
        help="Coste real / Coste teórico × 100. Mide cuánto del coste previsto "
             "de la OF ya se ha incurrido (avance económico, no de piezas).",
    )

    @api.depends(
        "sale_line_id",
        "procurement_group_id.sale_id",
    )
    def _compute_apunts_partner_id(self):
        for prod in self:
            # sudo: este campo (almacenado) se recalcula al escribir en la OF,
            # incluso desde un operario de planta que NO tiene acceso a las
            # líneas/pedidos de venta. Leemos la venta como superusuario para
            # no exigirle ese permiso (evita el error de acceso en la PDA).
            ps = prod.sudo()
            partner = False
            if "sale_line_id" in prod._fields and ps.sale_line_id:
                partner = ps.sale_line_id.order_id.partner_id
            elif "sale_id" in prod._fields and ps.sale_id:
                partner = ps.sale_id.partner_id
            elif "x_studio_venta" in prod._fields and ps.x_studio_venta:
                partner = ps.x_studio_venta.partner_id
            elif ps.procurement_group_id and ps.procurement_group_id.sale_id:
                partner = ps.procurement_group_id.sale_id.partner_id
            prod.apunts_partner_id = partner or False

    @api.depends("apunts_sale_amount", "apunts_cost_total_planned", "apunts_cost_total_real")
    def _compute_apunts_margen(self):
        # apunts_margen_pct y apunts_margen_real_pct se guardan como fracción (0..1)
        # — el widget percentage en la vista ya multiplica × 100 al mostrar.
        # Dos pares de campos: teórico (planned por BoM) vs real (fichado hasta ahora).
        # `apunts_margen_real_dudoso` marca cuando el real es 0 (OF sin empezar): el
        # margen real entonces es 100% artificial — la vista lo pinta en rojo.
        for prod in self:
            venta = prod.apunts_sale_amount or 0.0
            coste_teo = prod.apunts_cost_total_planned or 0.0
            coste_real = prod.apunts_cost_total_real or 0.0
            # Margen teórico (BoM)
            prod.apunts_margen_of = venta - coste_teo
            prod.apunts_margen_pct = (prod.apunts_margen_of / venta) if venta else 0.0
            # Margen real (fichado)
            prod.apunts_margen_real_of = venta - coste_real
            prod.apunts_margen_real_pct = (prod.apunts_margen_real_of / venta) if venta else 0.0
            # Flag de "sin datos reales"
            prod.apunts_margen_real_dudoso = (coste_real <= 0.0) and (venta > 0.0)
            # Factor de cobertura: venta / coste_real (objetivo JR: >= 1,35)
            prod.apunts_factor_cobertura = (venta / coste_real) if coste_real > 0 else 0.0
            # Avance económico: coste real / coste teórico × 100 (cuánto del coste
            # previsto ya se ha incurrido). Puede pasar de 100% si se sobrepasa.
            prod.apunts_avance_coste_pct = (coste_real / coste_teo * 100.0) if coste_teo > 0 else 0.0

    apunts_min_total_plan = fields.Float(
        string="Min totales (plan)",
        compute="_compute_apunts_minutos",
        store=True,
        help="Minutos planificados totales de la OF (suma duration_expected de todas las fases).",
    )
    apunts_min_unit_plan = fields.Float(
        string="Min/pieza (plan)",
        compute="_compute_apunts_minutos",
        store=True,
        help="Minutos planificados por pieza = total plan / cantidad a fabricar.",
    )
    apunts_min_real_total = fields.Float(
        string="Min reales (fichados)",
        compute="_compute_apunts_minutos",
        store=True,
        help="Minutos reales fichados acumulados en todas las fases de la OF.",
    )
    apunts_min_unit_real = fields.Float(
        string="Min/pieza (real)",
        compute="_compute_apunts_minutos",
        store=True,
        help="Minutos reales por pieza producida = real acumulado / piezas validadas.",
    )

    @api.depends(
        "product_qty",
        "qty_produced",
        "qty_producing",
        "workorder_ids.duration_expected",
        "workorder_ids.duration",
    )
    def _compute_apunts_minutos(self):
        # Min/pieza real: cascada de denominador para evitar 0 cuando hay fichajes pero
        # ninguna pieza validada todavía.
        #   1) qty_validada (apunts_qty_done = max(qty_produced, qty_producing))
        #   2) qty_producing crudo
        #   3) product_qty planificado (proyección "si todo se hiciera a este ritmo")
        for prod in self:
            total_plan = sum(prod.workorder_ids.mapped("duration_expected") or [0.0])
            total_real = sum(prod.workorder_ids.mapped("duration") or [0.0])
            qty_done = max(prod.qty_produced or 0.0, prod.qty_producing or 0.0)
            denom_real = qty_done or (prod.qty_producing or 0.0) or (prod.product_qty or 0.0)
            prod.apunts_min_total_plan = total_plan
            prod.apunts_min_unit_plan = (total_plan / prod.product_qty) if prod.product_qty else 0.0
            prod.apunts_min_real_total = total_real
            prod.apunts_min_unit_real = (total_real / denom_real) if denom_real else 0.0

    apunts_sale_amount = fields.Monetary(
        string="Venta (€)",
        compute="_compute_apunts_sale_amount",
        store=True,
        currency_field="company_currency_id",
        help=(
            "Importe que el cliente paga por las piezas de esta orden.\n"
            "\n"
            "Se busca en este orden, hasta encontrar uno:\n"
            "  1) Línea de pedido de venta vinculada directamente.\n"
            "  2) Pedido de venta vinculado.\n"
            "  3) Campo personalizado de venta (x_studio_venta).\n"
            "  4) Pedido de venta del grupo de aprovisionamiento (camino estándar Odoo).\n"
            "\n"
            "Sólo cuenta pedidos en estado CONFIRMADO (no draft, no cancel)."
        ),
    )

    @api.depends(
        "sale_line_id", "product_qty", "product_id",
        "x_studio_venta", "procurement_group_id.sale_id",
    )
    def _compute_apunts_sale_amount(self):
        # Solo cuenta SOs confirmados (estado 'sale' o 'done') Y con entrega no completada.
        # Si delivery_status == 'full' la venta YA NO es WIP (todo entregado al cliente),
        # se sale del WIP.
        # Cascada para encontrar el SO vinculado a la OF:
        #   1) sale_line_id (link directo a línea de pedido)
        #   2) sale_id (link directo a pedido completo)
        #   3) x_studio_venta (campo Studio JR)
        #   4) procurement_group_id.sale_id (camino estándar Odoo)
        VALID_STATES = ("sale", "done")
        for prod in self:
            if not isinstance(prod.id, int):
                prod.apunts_sale_amount = 0.0
                continue
            # sudo: campo almacenado que se recalcula al escribir en la OF desde
            # planta. Leemos el pedido/línea de venta como superusuario para no
            # exigir al operario acceso a ventas (evita el error en la PDA).
            ps = prod.sudo()
            so = False
            if "sale_line_id" in prod._fields and ps.sale_line_id:
                so = ps.sale_line_id.order_id
                if so.state in VALID_STATES and so.delivery_status != "full":
                    sol = ps.sale_line_id
                    qty_so = sol.product_uom_qty or 0.0
                    if qty_so > 0:
                        prod.apunts_sale_amount = (sol.price_subtotal or 0.0) * (prod.product_qty / qty_so)
                    else:
                        prod.apunts_sale_amount = sol.price_subtotal or 0.0
                else:
                    prod.apunts_sale_amount = 0.0
                continue
            if "sale_id" in prod._fields and ps.sale_id:
                so = ps.sale_id
            elif "x_studio_venta" in prod._fields and ps.x_studio_venta:
                so = ps.x_studio_venta
            elif ps.procurement_group_id and ps.procurement_group_id.sale_id:
                so = ps.procurement_group_id.sale_id
            if so and so.state in VALID_STATES and so.delivery_status != "full":
                sols = so.order_line.filtered(lambda l: l.product_id == prod.product_id)
                prod.apunts_sale_amount = sum(sols.mapped("price_subtotal")) if sols else (so.amount_untaxed or 0.0)
            else:
                prod.apunts_sale_amount = 0.0

    @api.depends("name")
    def _compute_apunts_of_short(self):
        for prod in self:
            n = prod.name or ""
            prod.apunts_of_short = n.split("/")[-1] if n else ""

    @api.depends(
        "state",
        "product_qty",
        "qty_produced",
        "qty_producing",
        "move_raw_ids.state",
        "move_raw_ids.product_qty",
        "move_raw_ids.quantity",
        "move_raw_ids.price_unit",
        "move_raw_ids.product_id",
        "workorder_ids.duration_expected",
        "workorder_ids.duration",
        "workorder_ids.workcenter_id.costs_hour",
        "workorder_ids.workcenter_id.apunts_amort_hour",
        "apunts_productivity_trigger",
    )
    def _compute_apunts_wip_costs(self):
        for prod in self:
            # Records nuevos sin guardar (NewId) no se pueden usar en SQL
            # crudo. Devolver valores por defecto y salir.
            if not isinstance(prod.id, int):
                prod.apunts_qty_pending = 0.0
                prod.apunts_cost_total_planned = 0.0
                prod.apunts_cost_total_real = 0.0
                prod.apunts_mat_real_total = 0.0
                prod.apunts_mo_real_total = 0.0
                prod.apunts_machine_real_total = 0.0
                prod.apunts_mat_planned_total = 0.0
                prod.apunts_mo_planned_total = 0.0
                prod.apunts_machine_planned_total = 0.0
                prod.apunts_bom_incompleta = False
                prod.apunts_is_wip = False
                continue

            qty_total = prod.product_qty or 0.0
            # Algunos operarios marcan cantidad en `qty_producing` sin validar
            # parcial. Usar el mayor de los dos como hecho real.
            qty_done = max(prod.qty_produced or 0.0, prod.qty_producing or 0.0)
            qty_pending = max(qty_total - qty_done, 0.0)

            mp_total_plan = self._apunts_mp_total_planned(prod)
            mo_total_plan, machine_total_plan, amort_total_plan = (
                self._apunts_workorder_totals_planned(prod)
            )
            mp_total_real = self._apunts_mp_total_real(prod)
            mo_total_real, machine_total_real, amort_total_real = (
                self._apunts_workorder_totals_real(prod)
            )

            # MP extra por reposición = importe REAL de los pedidos de compra de
            # reposición vinculados a la OF (no una estimación). Se cuenta desde
            # que existe la compra; las líneas de reposición se excluyen del
            # material consumido (en _apunts_mp_total_real) para no duplicar.
            mat_extra = self._apunts_reposicion_po_total(prod)
            prod.apunts_mat_reposicion_extra = mat_extra
            prod.apunts_qty_pending = qty_pending
            prod.apunts_cost_total_planned = (
                mp_total_plan + mo_total_plan + machine_total_plan + amort_total_plan
            )
            prod.apunts_cost_total_real = (
                mp_total_real + mat_extra + mo_total_real + machine_total_real + amort_total_real
            )
            prod.apunts_mat_real_total = mp_total_real + mat_extra
            prod.apunts_mo_real_total = mo_total_real
            prod.apunts_machine_real_total = machine_total_real
            prod.apunts_mat_planned_total = mp_total_plan
            prod.apunts_mo_planned_total = mo_total_plan
            prod.apunts_machine_planned_total = machine_total_plan
            prod.apunts_bom_incompleta = (
                mp_total_real > 50.0
                and mp_total_real > mp_total_plan * 1.5
            )
            prod.apunts_is_wip = self._apunts_compute_is_wip(prod)

    @staticmethod
    def _apunts_compute_is_wip(prod):
        # Records nuevos sin guardar no son WIP (no tienen ni id real).
        if not isinstance(prod.id, int):
            return False
        if prod.state not in ("confirmed", "progress", "to_close"):
            return False
        # JR a veces usa qty_producing (sin validar parcial) y a veces
        # qty_produced (al validar). Tomar el mayor para sacar del WIP las
        # OFs ya procesadas aunque sigan en estado "En proc".
        qty_done = max(prod.qty_produced or 0.0, prod.qty_producing or 0.0)
        if qty_done >= (prod.product_qty or 0.0) > 0:
            return False
        # WIP = OF con dinero comprometido. Dos vías:
        # 1) consumo físico marcado (move_raw.quantity > 0)
        # 2) PO con campo `fabricacion`=OF que ya se ha recibido (qty_received > 0).
        #    Cubre el caso JR donde el material está en taller pero el operario
        #    aún no ha validado el consumo en pantalla.
        for m in prod.move_raw_ids:
            if m.state == "cancel":
                continue
            if (m.quantity or 0.0) > 0:
                return True
        POL = prod.env["purchase.order.line"]
        if "fabricacion" in POL._fields:
            has_recv = POL.search_count([
                ("fabricacion", "=", prod.id),
                ("order_id.state", "in", ("purchase", "done")),
                ("qty_received", ">", 0),
            ])
            if has_recv:
                return True
        return False

    def _apunts_mp_total_planned(self, prod):
        total = 0.0
        for m in prod.move_raw_ids:
            if m.state == "cancel":
                continue
            qty = m.product_qty or 0.0
            price = self._apunts_get_product_cost(m.product_id, prod)
            total += qty * price
        return total

    def _apunts_mp_total_real(self, prod):
        # Punto 10 JR: coste REAL de materiales = cantidad CONSUMIDA en la OF
        # (move_raw.quantity, lo realmente UTILIZADO) × PRECIO del pedido de
        # compra vinculado a la OF (campo `fabricacion`).
        #   • Cuenta lo usado, no lo comprado: si compras 20 y usas 10, cuenta 10.
        #   • Valora al precio del PO (lo que costó comprarlo), no al coste estándar.
        #   • Si un material consumido no tiene PO vinculado, fallback a su coste
        #     estándar para no dejar el material sin valorar.
        POL = self.env["purchase.order.line"]
        precio_po = {}
        if "fabricacion" in POL._fields:
            dom = [
                ("fabricacion", "=", prod.id),
                ("order_id.state", "in", ("purchase", "done")),
            ]
            # Excluir compras de reposición: su coste se cuenta aparte
            # (apunts_mat_reposicion_extra) para no duplicarlo.
            if "apunts_es_reposicion" in POL._fields:
                dom.append(("apunts_es_reposicion", "=", False))
            pols = POL.search(dom)
            for pol in pols:
                if pol.price_unit:
                    precio = pol.price_unit
                    # Si la línea de compra está valorada por UNIDAD SECUNDARIA
                    # (p. ej. €/kg en barras/perfiles que se consumen en m), el
                    # price_unit es €/kg pero el consumo (move.quantity) está en m.
                    # Convertimos a €/UoM-base con el factor de la unidad
                    # secundaria (factor = base por secundaria, es decir m/kg):
                    #   €/m = €/kg ÷ (m/kg)
                    # Evita el error de multiplicar metros por un precio por kilo.
                    su = pol.secondary_uom_id
                    if su and su.factor:
                        precio = pol.price_unit / su.factor
                    precio_po[pol.product_id.id] = precio
        total = 0.0
        for m in prod.move_raw_ids:
            if m.state == "cancel":
                continue
            qty_consumida = m.quantity or 0.0
            if not qty_consumida:
                continue
            price = precio_po.get(m.product_id.id)
            if price is None:
                price = self._apunts_get_product_cost(m.product_id, prod)
            total += qty_consumida * price
        return total

    def _apunts_reposicion_po_total(self, prod):
        """Importe (price_subtotal) de las líneas de compra de REPOSICIÓN
        vinculadas a la OF. Cuenta desde que la compra existe (cualquier estado
        salvo cancelada). Es el coste REAL de material extra por rehacer piezas
        no validadas — sustituye a la estimación anterior."""
        POL = self.env["purchase.order.line"]
        if "fabricacion" not in POL._fields or "apunts_es_reposicion" not in POL._fields:
            return 0.0
        pols = POL.search([
            ("fabricacion", "=", prod.id),
            ("apunts_es_reposicion", "=", True),
            ("state", "not in", ("cancel",)),
        ])
        return sum(pols.mapped("price_subtotal"))

    def _apunts_material_real(self):
        # Override del módulo apunts_costes_of: una sola fuente de verdad
        # para el material real en ambos módulos (smart button COSTE OF y
        # columna EN CURSO real del WIP).
        self.ensure_one()
        return round(self._apunts_mp_total_real(self), 2)

    @staticmethod
    def _apunts_workorder_totals_planned(prod):
        # MO teórica: cascada idéntica a la real para que cuadre el "previsto":
        #   1) media hourly_cost de empleados asignados al workorder
        #   2) fallback wc.employee_costs_hour del centro de trabajo
        # Máquina: costs_hour del workcenter.
        # Amortización: apunts_amort_hour del workcenter.
        mo = machine = amort = 0.0
        for wo in prod.workorder_ids:
            wc = wo.workcenter_id
            hours = (wo.duration_expected or 0.0) / 60.0
            machine += hours * (wc.costs_hour or 0.0)
            amort += hours * (wc.apunts_amort_hour or 0.0)
            employees = wo.employee_ids if "employee_ids" in wo._fields else False
            avg_hour_cost = 0.0
            if employees:
                avg_hour_cost = sum(employees.mapped("hourly_cost")) / len(employees)
            if not avg_hour_cost:
                avg_hour_cost = wc.employee_costs_hour or 0.0
            mo += hours * avg_hour_cost
        return mo, machine, amort

    @staticmethod
    def _apunts_workorder_totals_real(prod):
        # Fuente única: productividades cerradas (date_end != NULL) de los workorders.
        # MO, máquina y amortización se prorratean cuando un empleado está fichado
        # simultáneamente en varias OFs. Registros sin empleado usan duración bruta.
        cr = prod.env.cr
        cr.execute("""
            SELECT
                COALESCE(SUM(p.duration / 60.0 * COALESCE(wc.costs_hour, 0)), 0)        AS machine,
                COALESCE(SUM(p.duration / 60.0 * COALESCE(wc.apunts_amort_hour, 0)), 0) AS amort
            FROM   mrp_workcenter_productivity p
            JOIN   mrp_workorder               wo ON wo.id = p.workorder_id
            JOIN   mrp_workcenter              wc ON wc.id = p.workcenter_id
            WHERE  wo.production_id = %s AND p.date_end IS NOT NULL AND p.employee_id IS NULL
        """, [prod.id])
        row = cr.fetchone() or (0.0, 0.0)
        machine_anon = float(row[0] or 0.0)
        amort_anon = float(row[1] or 0.0)
        mo = prod._apunts_prorated_emp_cost(prod.id, use_cascade=True)
        machine = machine_anon + prod._apunts_prorated_emp_cost(prod.id, use_center=True)
        amort = amort_anon + prod._apunts_prorated_cost_raw(prod.id, None, "COALESCE(wc.apunts_amort_hour, 0)")
        return mo, machine, amort

    def _apunts_get_product_cost(self, product, production=None):
        """Cascada: pol vinculada a la OF (campo `fabricacion`) → standard_price
        → POs recibidas → última PO confirmada → sellers."""
        if not product:
            return 0.0
        POL = self.env["purchase.order.line"]
        if production and "fabricacion" in POL._fields:
            pols = POL.search([
                ("fabricacion", "=", production.id),
                ("product_id", "=", product.id),
                ("order_id.state", "in", ("purchase", "done")),
            ])
            if pols:
                tq = sum(pols.mapped("product_qty"))
                ta = sum(pols.mapped("price_subtotal"))
                if tq > 0 and ta > 0:
                    return ta / tq
        if product.standard_price:
            return product.standard_price
        # Último stock.move incoming done con price_unit > 0. JR a veces
        # rellena el precio en la PO (que se traslada al move) sin
        # actualizar el standard_price del producto.
        last_move = self.env["stock.move"].search([
            ("product_id", "=", product.id),
            ("state", "=", "done"),
            ("picking_type_id.code", "=", "incoming"),
            ("price_unit", ">", 0),
        ], order="date desc", limit=1)
        if last_move and last_move.price_unit:
            return abs(last_move.price_unit)
        cr = self.env.cr
        cr.execute(
            """
            SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE pol.product_id = %s
              AND po.state IN ('purchase','done')
              AND pol.qty_received > 0
            """,
            [product.id],
        )
        row = cr.fetchone()
        v = float(row[0]) if row and row[0] else 0.0
        if v > 0:
            return v
        cr.execute(
            """
            SELECT pol.price_unit FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE pol.product_id = %s
              AND po.state IN ('purchase','done')
              AND pol.price_unit > 0
            ORDER BY po.date_order DESC NULLS LAST, po.id DESC LIMIT 1
            """,
            [product.id],
        )
        row = cr.fetchone()
        v = float(row[0]) if row and row[0] else 0.0
        if v > 0:
            return v
        sellers = product.seller_ids.sorted(
            key=lambda s: (s.sequence or 99, -(s.id or 0))
        )
        for s in sellers:
            if s.price and s.price > 0:
                return s.price
        return 0.0
