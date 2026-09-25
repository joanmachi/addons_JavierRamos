import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ApuntsDireccionResumen(models.TransientModel):
    """Panel único de Dirección: valor actual de cada KPI + botón que
    lleva a la vista existente donde se analiza en detalle. Los cálculos
    replican los criterios de los módulos de origen; el detalle manda."""

    _name = "apunts.direccion.resumen"
    _description = "Panel Dirección — KPIs globales"

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Panel Dirección"

    currency_id = fields.Many2one("res.currency", compute="_compute_kpis")

    # 1. Facturación
    fact_anual = fields.Monetary(string="Facturación año", compute="_compute_kpis", currency_field="currency_id")
    fact_semana = fields.Monetary(string="Facturación semana", compute="_compute_kpis", currency_field="currency_id")
    # 2. Pedidos
    pedidos_mes = fields.Monetary(string="Pedidos del mes", compute="_compute_kpis", currency_field="currency_id")
    pedidos_anual = fields.Monetary(string="Pedidos del año", compute="_compute_kpis", currency_field="currency_id")
    # 3. Cartera pendiente
    cartera_pendiente = fields.Monetary(string="Cartera pendiente", compute="_compute_kpis", currency_field="currency_id")
    # 4. Cobertura
    cobertura_meses = fields.Float(string="Cobertura (meses)", compute="_compute_kpis", digits=(16, 1))
    # 5. Tesorería
    tesoreria = fields.Monetary(string="Tesorería", compute="_compute_kpis", currency_field="currency_id")
    # 6. Cobros pendientes
    cobros_pendientes = fields.Monetary(string="Cobros pendientes", compute="_compute_kpis", currency_field="currency_id")
    # 7. EBITDA del año (misma cascada que el P&G por Periodos)
    ebitda_anual = fields.Monetary(string="EBITDA año", compute="_compute_kpis", currency_field="currency_id")
    ebitda_pct = fields.Float(string="EBITDA %", compute="_compute_kpis", digits=(16, 1))
    # 8. Entregas en fecha
    entregas_mes_pct = fields.Float(string="Entregas en fecha (mes) %", compute="_compute_kpis", digits=(16, 1))
    entregas_anual_pct = fields.Float(string="Entregas en fecha (año) %", compute="_compute_kpis", digits=(16, 1))
    # 9. Horas productivas
    horas_prod_pct = fields.Float(string="Jornada cumplida (mes) %", compute="_compute_kpis", digits=(16, 1))
    # 10. WIP
    wip_valor = fields.Monetary(string="Valor WIP", compute="_compute_kpis", currency_field="currency_id")
    # Objetivos del cuadro de mando (comparación real vs meta)
    objetivos_html = fields.Html(string="Objetivos", compute="_compute_objetivos_html",
                                 sanitize=False)

    # ── Objetivos vs real ─────────────────────────────────────────────────────

    @api.depends_context("uid")
    def _compute_objetivos_html(self):
        """Tabla 'objetivo vs real' con el % de cumplimiento de cada indicador
        que tenga meta definida (Dirección → Objetivos del cuadro de mando)."""
        hoy = fields.Date.context_today(self)
        # Parte del año transcurrida, para los objetivos anuales acumulativos
        ini_ano = hoy.replace(month=1, day=1)
        dias_ano = (hoy.replace(month=12, day=31) - ini_ano).days + 1
        transcurrido = ((hoy - ini_ano).days + 1) / dias_ano
        for rec in self:
            try:
                objetivos = self.env["apunts.direccion.objetivo"].sudo().search([])
            except Exception:
                rec.objetivos_html = ""
                continue
            if not objetivos:
                rec.objetivos_html = (
                    "<p class='text-muted'>No hay objetivos definidos todavía. "
                    "Se configuran en <b>Dirección → Objetivos del cuadro de mando</b>.</p>")
                continue
            simbolo = self.env.company.currency_id.symbol or "€"
            filas = []
            for obj in objetivos:
                real = rec[obj.kpi] if obj.kpi in rec._fields else 0.0
                meta = obj.valor
                if obj.prorratear:
                    meta = meta * transcurrido
                if not meta:
                    continue
                pct = real / meta * 100.0
                # "Cuanto menos, mejor" (p. ej. cobros pendientes): se invierte
                cumple = (real >= meta) if obj.mejor_es_mayor else (real <= meta)
                if cumple:
                    color, icono = "#15803d", "✔"
                elif (pct >= 85 if obj.mejor_es_mayor else pct <= 115):
                    color, icono = "#b45309", "≈"
                else:
                    color, icono = "#be123c", "✖"
                es_pct = obj.kpi.endswith("_pct")
                es_meses = obj.kpi == "cobertura_meses"
                if es_pct:
                    fmt = lambda v: "%.1f %%" % v
                elif es_meses:
                    fmt = lambda v: "%.1f meses" % v
                else:
                    fmt = lambda v: "{:,.0f} {}".format(v, simbolo).replace(",", ".")
                nota = " <span class='text-muted'>(parte del año transcurrida)</span>" if obj.prorratear else ""
                filas.append(
                    "<tr>"
                    "<td>%s</td>"
                    "<td class='text-end fw-semibold'>%s</td>"
                    "<td class='text-end'>%s%s</td>"
                    "<td class='text-end fw-bold' style='color:%s'>%s %.0f %%</td>"
                    "</tr>" % (obj.display_name, fmt(real), fmt(meta), nota, color, icono, pct)
                )
            rec.objetivos_html = (
                "<table class='table table-sm table-striped mb-0'>"
                "<thead><tr><th>Indicador</th><th class='text-end'>Real</th>"
                "<th class='text-end'>Objetivo</th>"
                "<th class='text-end'>Cumplimiento</th></tr></thead>"
                "<tbody>%s</tbody></table>" % "".join(filas)
            )

    def action_abrir(self):
        """Abre la pantalla cuyo XMLID viene en el contexto del botón.

        Lo usan los accesos de la pestaña "Otros paneles": un único método, y
        cada botón dice a dónde va. Vale igual para acciones normales y para
        acciones servidor (dashboards de contabilidad, WIP, taller...)."""
        xmlid = self.env.context.get("apunts_xmlid")
        if not xmlid:
            raise UserError("Este acceso no tiene destino configurado.")
        accion = self.env.ref(xmlid, raise_if_not_found=False)
        if not accion:
            raise UserError(
                "Esa pantalla no está disponible en esta instalación.\n\n"
                "Puede que el módulo que la aporta no esté instalado (%s)." % xmlid
            )
        # sudo: el panel lo abre dirección (perfil contable de solo lectura) y
        # las acciones son de otros módulos. El permiso sobre los datos lo sigue
        # comprobando Odoo al abrir la pantalla de destino.
        if accion._name == "ir.actions.server":
            return accion.sudo().run()
        return accion.sudo().read()[0]

    def action_ver_objetivos(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Objetivos del cuadro de mando",
            "res_model": "apunts.direccion.objetivo",
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
        }

    # ── Cálculo ───────────────────────────────────────────────────────────────

    def _sql_uno(self, query, params=()):
        self.env.cr.execute(query, params)
        row = self.env.cr.fetchone()
        return row if row else ()

    @api.depends_context("uid")
    def _compute_kpis(self):
        hoy = fields.Date.context_today(self)
        ini_ano = hoy.replace(month=1, day=1)
        ini_mes = hoy.replace(day=1)
        ini_semana = hoy - timedelta(days=hoy.weekday())
        dt_mes = datetime.combine(ini_mes, time.min)
        dt_ano = datetime.combine(ini_ano, time.min)
        for rec in self:
            rec.currency_id = self.env.company.currency_id
            # Defaults (por si alguna fuente falla, el panel no se rompe)
            rec.fact_anual = rec.fact_semana = 0.0
            rec.pedidos_mes = rec.pedidos_anual = 0.0
            rec.cartera_pendiente = 0.0
            rec.cobertura_meses = 0.0
            rec.tesoreria = rec.cobros_pendientes = 0.0
            rec.ebitda_anual = rec.ebitda_pct = 0.0
            rec.entregas_mes_pct = rec.entregas_anual_pct = 0.0
            rec.horas_prod_pct = 0.0
            rec.wip_valor = 0.0

            # 1) Facturación = ingresos por ventas contabilizados (cuentas 70x),
            #    la misma cifra que el P&G, el Tablero y el Análisis de ventas
            try:
                cid = self.env.company.id
                row = self._sql_uno(
                    """
                    SELECT COALESCE(SUM(CASE WHEN aml.date >= %s THEN -aml.balance END), 0),
                           COALESCE(SUM(CASE WHEN aml.date >= %s THEN -aml.balance END), 0)
                    FROM account_move_line aml
                    JOIN account_account aa ON aa.id = aml.account_id
                    WHERE aml.parent_state = 'posted' AND aml.company_id = %s
                      AND aa.code_store->>%s LIKE '70%%' AND aml.date >= %s
                    """,
                    (ini_ano, ini_semana, cid, str(cid), ini_ano),
                )
                rec.fact_anual, rec.fact_semana = float(row[0] or 0), float(row[1] or 0)
            except Exception as e:
                _logger.warning("Panel dirección: facturación falló: %s", e)

            # 2) Entrada de pedidos (confirmados, base imponible)
            try:
                row = self._sql_uno(
                    """
                    SELECT COALESCE(SUM(CASE WHEN date_order >= %s THEN amount_untaxed END), 0),
                           COALESCE(SUM(amount_untaxed), 0)
                    FROM sale_order
                    WHERE state IN ('sale', 'done') AND date_order >= %s
                    """,
                    (dt_mes, dt_ano),
                )
                rec.pedidos_mes, rec.pedidos_anual = float(row[0] or 0), float(row[1] or 0)
            except Exception as e:
                _logger.warning("Panel dirección: pedidos falló: %s", e)

            # 3) Cartera pendiente (vendido y aún no entregado, sin impuestos)
            try:
                row = self._sql_uno(
                    """
                    SELECT COALESCE(SUM(
                        (sol.product_uom_qty - sol.qty_delivered)
                        * sol.price_unit * (1 - COALESCE(sol.discount, 0) / 100.0)
                    ), 0)
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    WHERE so.state IN ('sale', 'done')
                      AND sol.display_type IS NULL
                      AND sol.product_uom_qty > sol.qty_delivered
                    """
                )
                rec.cartera_pendiente = float(row[0] or 0)
            except Exception as e:
                _logger.warning("Panel dirección: cartera falló: %s", e)

            # 4) Cobertura: horas pendientes / ritmo real mensual (30 días)
            try:
                centros = self.env["mrp.workcenter"].sudo().search([("active", "=", True)])
                pendientes = sum(centros.mapped("apunts_horas_pendientes"))
                ritmo_mes = sum(centros.mapped("apunts_horas_reales_30d"))
                rec.cobertura_meses = pendientes / ritmo_mes if ritmo_mes else 0.0
            except Exception as e:
                _logger.warning("Panel dirección: cobertura falló: %s", e)

            # 5) Tesorería (saldo de cuentas de liquidez, asientos publicados)
            try:
                row = self._sql_uno(
                    """
                    SELECT COALESCE(SUM(aml.balance), 0)
                    FROM account_move_line aml
                    JOIN account_account aa ON aa.id = aml.account_id
                    WHERE aa.account_type = 'asset_cash'
                      AND aml.parent_state = 'posted'
                    """
                )
                rec.tesoreria = float(row[0] or 0)
            except Exception as e:
                _logger.warning("Panel dirección: tesorería falló: %s", e)

            # 6) Cobros pendientes (residual de facturas de cliente)
            try:
                row = self._sql_uno(
                    """
                    SELECT COALESCE(SUM(amount_residual_signed), 0)
                    FROM account_move
                    WHERE move_type IN ('out_invoice', 'out_refund')
                      AND state = 'posted'
                      AND payment_state IN ('not_paid', 'partial')
                    """
                )
                rec.cobros_pendientes = float(row[0] or 0)
            except Exception as e:
                _logger.warning("Panel dirección: cobros falló: %s", e)

            # 7) EBITDA del año: la misma cascada por bloques del P&G por Periodos
            #    (motor de KPIs), acumulada desde el 1 de enero. El margen de
            #    contribución se retiró a petición de la empresa.
            try:
                c = self.env["apunts.kpi.motor"].sudo()._cascada(ini_ano, hoy)
                rec.ebitda_anual = c["ebitda"]
                rec.ebitda_pct = c["ebitda"] / c["fact"] * 100.0 if c["fact"] else 0.0
            except Exception as e:
                _logger.warning("Panel dirección: EBITDA falló: %s", e)

            # 8) Entregas en fecha (albarán validado ≤ fecha comprometida)
            try:
                row = self._sql_uno(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE sp.apunts_en_fecha AND sp.date_done >= %s),
                      COUNT(*) FILTER (WHERE sp.date_done >= %s),
                      COUNT(*) FILTER (WHERE sp.apunts_en_fecha),
                      COUNT(*)
                    FROM stock_picking sp
                    JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                    WHERE spt.code = 'outgoing'
                      AND sp.state = 'done'
                      AND sp.apunts_fecha_limite IS NOT NULL
                      AND sp.date_done >= %s
                    """,
                    (dt_mes, dt_mes, dt_ano),
                )
                ok_mes, tot_mes, ok_ano, tot_ano = [int(x or 0) for x in row]
                rec.entregas_mes_pct = ok_mes / tot_mes * 100.0 if tot_mes else 0.0
                rec.entregas_anual_pct = ok_ano / tot_ano * 100.0 if tot_ano else 0.0
            except Exception as e:
                _logger.warning("Panel dirección: entregas falló: %s", e)

            # 9) Horas productivas: mismo cálculo que "Jornada cumplida" de
            #    los KPIs de fichaje (mes en curso)
            try:
                # sudo: el panel lo abre un perfil contable sin acceso al modelo
                # de taller; sin sudo, el create fallaba y el KPI caía a 0.
                kpi = self.env["apunts.taller.kpi"].sudo().create({})
                kpi._calcular()
                rec.horas_prod_pct = kpi.pct_cumplimiento
            except Exception as e:
                _logger.warning("Panel dirección: horas productivas falló: %s", e)

            # 10) Valor WIP: coste real acumulado de las OFs en curso
            try:
                wip = self.env["mrp.production"].sudo().search([("apunts_is_wip", "=", True)])
                rec.wip_valor = sum(wip.mapped("apunts_cost_total_real"))
            except Exception as e:
                _logger.warning("Panel dirección: WIP falló: %s", e)

    # ── Botones: llevar a la vista de detalle ya existente ────────────────────

    def _run_srv(self, xmlid):
        return self.env.ref(xmlid).sudo().run()

    def action_ver_facturacion(self):
        # Facturación REAL por mes (facturas de cliente), no pedidos: antes
        # apuntaba a la 'Evolución mensual' de lira, que en realidad son
        # pedidos (amount_untaxed de sale.order), y por eso se solapaba con la
        # tarjeta de Pedidos.
        return self._run_srv(
            "apunts_jr_dashboard_direccion.apunts_action_facturacion_mensual_srv"
        )

    def action_ver_pedidos(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_sales_analysis")

    def action_ver_cartera(self):
        """Gráfica que reparte la cartera pendiente por semana de entrega
        comprometida (¿cuándo vamos a entregar lo vendido?). Son las mismas
        líneas del informe 'Pedidos pendientes de entrega' de lira, abiertas
        directamente en la gráfica en vez de en su ficha."""
        informe = self.env["lira.pending.delivery"].create({})
        informe._compute_and_store()
        ref = self.env.ref
        return {
            "type": "ir.actions.act_window",
            "name": "Cartera pendiente de servir · ¿cuándo se entrega?",
            "res_model": "lira.pending.delivery.line",
            "view_mode": "graph,pivot,list",
            "views": [
                (ref("apunts_jr_dashboard_direccion.apunts_view_cartera_semana_graph").id, "graph"),
                (ref("lira_dashboard_contabilidad.view_lira_pending_delivery_line_pivot").id, "pivot"),
                (ref("lira_dashboard_contabilidad.view_lira_pending_delivery_line_list").id, "list"),
            ],
            "search_view_id": (ref("lira_dashboard_contabilidad.view_lira_pending_delivery_line_search").id, "search"),
            "domain": [("user_id", "=", self.env.user.id)],
            "context": {"create": False, "delete": False, "fill_temporal": True},
            "target": "current",
        }

    def action_ver_cobertura(self):
        return self._run_srv("apunts_jr_carga_centros.apunts_action_carga_resumen_srv")

    def action_ver_tesoreria(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_dashboard")

    def action_ver_cobros(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_aging")

    def action_ver_ebitda(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_pnl_period")

    def action_ver_entregas(self):
        hoy = fields.Date.context_today(self)
        ini_ano = fields.Datetime.to_string(
            datetime.combine(hoy.replace(month=1, day=1), time.min)
        )
        ref = self.env.ref
        return {
            "type": "ir.actions.act_window",
            "name": "Entregas del año (en fecha / tarde)",
            "res_model": "stock.picking",
            "view_mode": "list,graph,pivot,form",
            "views": [
                (ref("apunts_jr_dashboard_direccion.apunts_view_picking_entregas_list").id, "list"),
                (ref("apunts_jr_dashboard_direccion.apunts_view_picking_entregas_graph").id, "graph"),
                (ref("apunts_jr_dashboard_direccion.apunts_view_picking_entregas_pivot").id, "pivot"),
                (False, "form"),
            ],
            "domain": [
                ("picking_type_id.code", "=", "outgoing"),
                ("state", "=", "done"),
                ("apunts_fecha_limite", "!=", False),
                ("date_done", ">=", ini_ano),
            ],
            # Agrupado por semana de entrega: en la lista se ven las semanas con su
            # desvío medio y la gráfica sale directamente con las semanas en
            # horizontal (semanas sin entregas a cero gracias a fill_temporal).
            "context": {"search_default_apunts_group_semana": 1, "fill_temporal": True},
        }

    def action_ver_horas(self):
        return self._run_srv("apunts_jr_gestion_taller.action_apunts_taller_kpi")

    def action_ver_wip(self):
        return self._run_srv("apunts_jr_wip_costes_of.apunts_action_wip_resumen_srv")

    def action_ver_evolucion(self):
        return self.env.ref(
            "apunts_jr_dashboard_direccion.apunts_action_direccion_snapshot"
        ).read()[0]

    @api.model
    def action_open_resumen(self):
        rec = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Panel Dirección",
            "res_model": "apunts.direccion.resumen",
            "view_mode": "form",
            "view_id": self.env.ref(
                "apunts_jr_dashboard_direccion.apunts_direccion_resumen_form"
            ).id,
            "res_id": rec.id,
            "target": "current",
        }
