import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models

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
    # 7. Margen bruto
    margen_bruto = fields.Monetary(string="Margen bruto año", compute="_compute_kpis", currency_field="currency_id")
    margen_bruto_pct = fields.Float(string="Margen bruto %", compute="_compute_kpis", digits=(16, 1))
    # 8. Entregas en fecha
    entregas_mes_pct = fields.Float(string="Entregas en fecha (mes) %", compute="_compute_kpis", digits=(16, 1))
    entregas_anual_pct = fields.Float(string="Entregas en fecha (año) %", compute="_compute_kpis", digits=(16, 1))
    # 9. Horas productivas
    horas_prod_pct = fields.Float(string="Jornada cumplida (mes) %", compute="_compute_kpis", digits=(16, 1))
    # 10. WIP
    wip_valor = fields.Monetary(string="Valor WIP", compute="_compute_kpis", currency_field="currency_id")

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
            rec.margen_bruto = rec.margen_bruto_pct = 0.0
            rec.entregas_mes_pct = rec.entregas_anual_pct = 0.0
            rec.horas_prod_pct = 0.0
            rec.wip_valor = 0.0

            # 1) Facturación (facturas de cliente publicadas, base imponible)
            try:
                row = self._sql_uno(
                    """
                    SELECT COALESCE(SUM(CASE WHEN date >= %s THEN amount_untaxed_signed END), 0),
                           COALESCE(SUM(CASE WHEN date >= %s THEN amount_untaxed_signed END), 0)
                    FROM account_move
                    WHERE move_type IN ('out_invoice', 'out_refund')
                      AND state = 'posted'
                      AND date >= %s
                    """,
                    (ini_ano, ini_semana, ini_ano),
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
                centros = self.env["mrp.workcenter"].search([("active", "=", True)])
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

            # 7) Margen bruto año: ingresos − coste directo (tipo de cuenta
            #    "coste directo de ventas" o cuentas 60x)
            try:
                ctas_60 = tuple(
                    self.env["account.account"].search([("code", "=like", "60%")]).ids
                ) or (0,)
                row = self._sql_uno(
                    """
                    SELECT
                      COALESCE(SUM(CASE WHEN aa.account_type IN ('income', 'income_other')
                                        THEN -aml.balance END), 0) AS ingresos,
                      COALESCE(SUM(CASE WHEN aa.account_type = 'expense_direct_cost'
                                          OR aml.account_id IN %s
                                        THEN aml.balance END), 0) AS coste
                    FROM account_move_line aml
                    JOIN account_account aa ON aa.id = aml.account_id
                    WHERE aml.parent_state = 'posted' AND aml.date >= %s
                    """,
                    (ctas_60, ini_ano),
                )
                ingresos, coste = float(row[0] or 0), float(row[1] or 0)
                rec.margen_bruto = ingresos - coste
                rec.margen_bruto_pct = (
                    rec.margen_bruto / ingresos * 100.0 if ingresos else 0.0
                )
            except Exception as e:
                _logger.warning("Panel dirección: margen falló: %s", e)

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
                kpi = self.env["apunts.taller.kpi"].create({})
                kpi._calcular()
                rec.horas_prod_pct = kpi.pct_cumplimiento
            except Exception as e:
                _logger.warning("Panel dirección: horas productivas falló: %s", e)

            # 10) Valor WIP: coste real acumulado de las OFs en curso
            try:
                wip = self.env["mrp.production"].search([("apunts_is_wip", "=", True)])
                rec.wip_valor = sum(wip.mapped("apunts_cost_total_real"))
            except Exception as e:
                _logger.warning("Panel dirección: WIP falló: %s", e)

    # ── Botones: llevar a la vista de detalle ya existente ────────────────────

    def _run_srv(self, xmlid):
        return self.env.ref(xmlid).sudo().run()

    def action_ver_facturacion(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_sales_monthly")

    def action_ver_pedidos(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_sales_analysis")

    def action_ver_cartera(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_pending_delivery")

    def action_ver_cobertura(self):
        return self._run_srv("apunts_jr_carga_centros.apunts_action_carga_resumen_srv")

    def action_ver_tesoreria(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_dashboard")

    def action_ver_cobros(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_aging")

    def action_ver_margen(self):
        return self._run_srv("lira_dashboard_contabilidad.action_lira_pnl_period")

    def action_ver_entregas(self):
        hoy = fields.Date.context_today(self)
        ini_ano = fields.Datetime.to_string(
            datetime.combine(hoy.replace(month=1, day=1), time.min)
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Entregas del año (en fecha / tarde)",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [
                ("picking_type_id.code", "=", "outgoing"),
                ("state", "=", "done"),
                ("apunts_fecha_limite", "!=", False),
                ("date_done", ">=", ini_ano),
            ],
            "context": {"search_default_apunts_group_en_fecha": 1},
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
