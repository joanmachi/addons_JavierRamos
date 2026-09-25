"""Motor de los KPIs de la reunión semanal de Dirección.

Calcula el valor de cada KPI para una semana ISO (lunes a domingo) a partir de
los datos de Odoo, siguiendo las reglas temporales que fijó la empresa:

  · € flujo   → lo generado en ESA semana (facturación, pedidos).
  · € saldo   → la foto al cierre de la semana (tesorería, cobros pendientes,
                cartera, fabricación en curso).
  · % económicos y financieros → acumulado desde el 1 de enero hasta el cierre
                de la semana (margen, EBITDA, COV, EDV...).
  · % operativos → solo la actividad de ESA semana (eficiencia, entregas...).
  · ratios y días → foto del ratio al cierre.

Casi todo se puede reconstruir hacia atrás desde la contabilidad, los pedidos
y los fichajes. Lo que es una foto de un instante (cartera pendiente, WIP) se
recupera de las fotos diarias que ya guardaba el panel; si no hay foto de esa
semana, se deja vacío en vez de inventar un cero.
"""

import logging
from datetime import date, datetime, time, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Primer día ISO que se historifica (semana 1 de 2026)
PRIMER_LUNES = date(2025, 12, 29)

# Horizonte máximo de la autonomía de tesorería (días)
DAT_HORIZONTE = 365

# KPIs que son una foto de un instante: hacia atrás salen de las fotos del panel
KPIS_FOTO = ("cartera_pendiente", "cdc", "wip_valor")


class ApuntsKpiMotor(models.AbstractModel):
    _name = "apunts.kpi.motor"
    _description = "Motor de cálculo de los KPIs de Dirección"

    # ══ Utilidades ═══════════════════════════════════════════════════════════

    def _cid(self):
        return self.env.company.id

    def _uno(self, query, params=()):
        self.env.cr.execute(query, params)
        row = self.env.cr.fetchone()
        return row if row else ()

    def _num(self, query, params=()):
        row = self._uno(query, params)
        return float(row[0] or 0.0) if row else 0.0

    @staticmethod
    def _div(a, b, mult=1.0):
        return (a / b * mult) if b else None

    @staticmethod
    def _dias_productivos(desde, hasta):
        """Días de lunes a viernes entre dos fechas, ambas incluidas."""
        n, d = 0, desde
        while d <= hasta:
            if d.weekday() < 5:
                n += 1
            d += timedelta(days=1)
        return n

    @staticmethod
    def _lunes_de(fecha):
        return fecha - timedelta(days=fecha.weekday())

    # ── Contabilidad ─────────────────────────────────────────────────────────

    def _balance_asof(self, hasta):
        """Saldos del balance a una fecha, por tipo de cuenta (misma definición
        que el Dashboard KPIs: se mantiene a petición de la empresa)."""
        cid = self._cid()
        self.env.cr.execute("""
            SELECT aa.account_type, COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s AND aml.date <= %s
            GROUP BY aa.account_type""", (cid, hasta))
        por_tipo = {r[0]: float(r[1] or 0.0) for r in self.env.cr.fetchall()}
        existencias = self._num("""
            SELECT COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s AND aml.date <= %s
              AND aa.code_store->>%s LIKE '3%%'""", (cid, hasta, str(cid)))

        def t(*tipos):
            return sum(por_tipo.get(x, 0.0) for x in tipos)

        activo_c = t("asset_receivable", "asset_cash", "asset_current", "asset_prepayments")
        activo_nc = t("asset_non_current", "asset_fixed")
        pasivo_c = -t("liability_payable", "liability_current", "liability_credit_card")
        pasivo_nc = -t("liability_non_current")
        return {
            "clientes": t("asset_receivable"),
            "tesoreria": t("asset_cash"),
            "existencias": existencias,
            "activo_c": activo_c,
            "activo_t": activo_c + activo_nc,
            "proveedores": -t("liability_payable"),
            "pasivo_c": pasivo_c,
            "pasivo_t": pasivo_c + pasivo_nc,
            "patrimonio": (activo_c + activo_nc) - (pasivo_c + pasivo_nc),
        }

    def _cascada(self, desde, hasta):
        """Cuenta de resultados en cascada entre dos fechas, con la
        clasificación de costes de la empresa (lira.cuenta.bloque). Es la misma
        cascada que el P&G por Periodos."""
        cid = self._cid()
        mapa = self.env["lira.cuenta.bloque"].sudo().mapa()
        self.env.cr.execute("""
            SELECT aa.code_store->>%s AS code, COALESCE(SUM(aml.debit - aml.credit), 0)
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aml.date >= %s AND aml.date <= %s
              AND (aa.code_store->>%s LIKE '6%%' OR aa.code_store->>%s LIKE '7%%')
            GROUP BY 1""", (str(cid), cid, desde, hasta, str(cid), str(cid)))
        c = {k: 0.0 for k in ("fact", "otros", "variacion", "ingfin", "variables_directos",
                              "semivariables", "fijos_operativos", "estructura",
                              "amortizaciones", "financieros", "sin_clasificar")}
        pref2 = {}
        for code, neto in self.env.cr.fetchall():
            code, neto = code or "", float(neto or 0.0)
            pref2[code[:2]] = pref2.get(code[:2], 0.0) + neto
            if code.startswith("70"):
                c["fact"] += -neto
            elif code.startswith("71"):
                c["variacion"] += -neto
            elif code.startswith("76"):
                c["ingfin"] += -neto
            elif code.startswith("7"):
                c["otros"] += -neto
            elif code in mapa:
                c[mapa[code]] += neto
            elif code.startswith("68"):
                c["amortizaciones"] += neto
            elif code.startswith("66"):
                c["financieros"] += neto
            elif code.startswith("6"):
                c["sin_clasificar"] += neto
        c["ebitda"] = (c["fact"] + c["otros"] + c["variacion"]
                       - c["variables_directos"] - c["semivariables"]
                       - c["fijos_operativos"] - c["estructura"] - c["sin_clasificar"])
        c["ebit"] = c["ebitda"] - c["amortizaciones"]
        c["resultado"] = c["ebit"] - c["financieros"] + c["ingfin"]
        c["compras"] = sum(pref2.get(p, 0.0) for p in ("60", "61", "62"))
        return c

    # ── Taller ───────────────────────────────────────────────────────────────

    def _horas_union(self, ini, fin, solo_planta=False):
        """Horas de persona en órdenes SIN contar dos veces los ratos con varias
        máquinas a la vez: se unen los fichajes solapados de cada operario."""
        extra = ""
        if solo_planta:
            # Planta = marcados en la ficha del empleado (pestaña Taller)
            extra = " AND COALESCE(e.apunts_planta, FALSE) = TRUE"
        self.env.cr.execute("""
            SELECT p.employee_id, p.date_start, p.date_end
            FROM mrp_workcenter_productivity p
            JOIN hr_employee e ON e.id = p.employee_id
            WHERE p.date_end IS NOT NULL AND p.employee_id IS NOT NULL
              AND p.date_end >= %%s AND p.date_end < %%s %s
            ORDER BY p.employee_id, p.date_start""" % extra, (ini, fin))
        total, emp_act, ini_tr, fin_tr = 0.0, None, None, None
        for emp, ds, de in self.env.cr.fetchall():
            if emp != emp_act:
                if ini_tr is not None:
                    total += (fin_tr - ini_tr).total_seconds()
                emp_act, ini_tr, fin_tr = emp, ds, de
                continue
            if ds > fin_tr:
                total += (fin_tr - ini_tr).total_seconds()
                ini_tr, fin_tr = ds, de
            else:
                fin_tr = max(fin_tr, de)
        if ini_tr is not None:
            total += (fin_tr - ini_tr).total_seconds()
        return total / 3600.0

    # ── Fotos guardadas por el panel (para las semanas pasadas) ──────────────

    def _foto_panel(self, kpi, lunes, domingo):
        """Último valor que el panel guardó de ese KPI dentro de la semana."""
        self.env.cr.execute("""
            SELECT valor FROM apunts_direccion_snapshot
            WHERE kpi = %s AND fecha >= %s AND fecha <= %s
            ORDER BY fecha DESC LIMIT 1""", (kpi, lunes, domingo))
        row = self.env.cr.fetchone()
        return float(row[0]) if row else None

    def _foto_panel_arrastrada(self, kpi, lunes, domingo):
        """Foto de la semana; si no la hay y esa semana no hubo actividad de
        taller (ni fichajes de máquina ni OF cerradas: vacaciones), vale la
        última foto anterior, porque el dato no pudo cambiar. Con actividad y
        sin foto, no se inventa nada."""
        valor = self._foto_panel(kpi, lunes, domingo)
        if valor is not None:
            return valor
        fin_dt = domingo + timedelta(days=1)
        actividad = self._num("""
            SELECT (SELECT COUNT(*) FROM mrp_workcenter_productivity
                     WHERE date_end >= %s AND date_end < %s)
                 + (SELECT COUNT(*) FROM mrp_production
                     WHERE state = 'done' AND date_finished >= %s AND date_finished < %s)""",
            (lunes, fin_dt, lunes, fin_dt))
        if actividad:
            return None
        self.env.cr.execute("""
            SELECT valor FROM apunts_direccion_snapshot
            WHERE kpi = %s AND fecha < %s ORDER BY fecha DESC LIMIT 1""", (kpi, lunes))
        row = self.env.cr.fetchone()
        return float(row[0]) if row else None

    def _cartera_asof(self, fin_dt):
        """Cartera pendiente de servir tal y como estaba en ese instante: pedidos
        confirmados hasta entonces menos lo entregado hasta entonces (los
        albaranes llevan fecha, así que se reconstruye para cualquier semana)."""
        return self._num("""
            SELECT COALESCE(SUM(GREATEST(sol.product_uom_qty - COALESCE(d.qty, 0), 0)
                                * sol.price_unit * (1 - COALESCE(sol.discount, 0) / 100.0)), 0)
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            LEFT JOIN (
                SELECT m.sale_line_id,
                       SUM(CASE WHEN ld.usage = 'customer' THEN m.product_uom_qty
                                ELSE -m.product_uom_qty END) AS qty
                FROM stock_move m
                JOIN stock_location ld ON ld.id = m.location_dest_id
                JOIN stock_location lo ON lo.id = m.location_id
                WHERE m.state = 'done' AND m.date < %s
                  AND (ld.usage = 'customer' OR lo.usage = 'customer')
                GROUP BY m.sale_line_id) d ON d.sale_line_id = sol.id
            WHERE so.state IN ('sale', 'done') AND sol.display_type IS NULL
              AND so.date_order < %s""", (fin_dt, fin_dt))

    # ── DAT: días de autonomía de tesorería ──────────────────────────────────

    def _dat(self, hoy=None, con_proyeccion=False):
        """Primer día en que la tesorería proyectada se queda a cero.

        Tesorería de hoy + cobros previstos (vencimientos de clientes) − pagos
        previstos (vencimientos de proveedores) − pagos recurrentes que no
        existen como vencimientos (nóminas, Seguridad Social, impuestos...),
        día a día durante un año."""
        hoy = hoy or fields.Date.context_today(self)
        cid = self._cid()
        tesoreria = self._num("""
            SELECT COALESCE(SUM(aml.balance), 0) FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aa.account_type = 'asset_cash' AND aml.parent_state = 'posted'
              AND aml.company_id = %s AND aml.date <= %s""", (cid, hoy))
        # Pendiente A ESA FECHA: saldo de cada vencimiento menos lo conciliado
        # hasta entonces (account_partial_reconcile.max_date). Así el DAT se
        # puede reconstruir hacia atrás y no depende del estado de hoy.
        self.env.cr.execute("""
            SELECT COALESCE(aml.date_maturity, aml.date) AS f,
                   COALESCE(SUM(CASE WHEN aa.account_type = 'asset_receivable'
                                     THEN aml.balance - COALESCE(p.pagado, 0) END), 0),
                   COALESCE(SUM(CASE WHEN aa.account_type = 'liability_payable'
                                     THEN -(aml.balance - COALESCE(p.pagado, 0)) END), 0)
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            LEFT JOIN (
                SELECT line_id, SUM(amount) AS pagado FROM (
                    SELECT debit_move_id AS line_id, amount
                    FROM account_partial_reconcile WHERE max_date <= %s
                    UNION ALL
                    SELECT credit_move_id, -amount
                    FROM account_partial_reconcile WHERE max_date <= %s
                ) x GROUP BY line_id
            ) p ON p.line_id = aml.id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aml.date <= %s
              AND aa.account_type IN ('asset_receivable', 'liability_payable')
            GROUP BY 1 ORDER BY 1""", (hoy, hoy, cid, hoy))
        vencimientos = {}
        for f, cob, pag in self.env.cr.fetchall():
            f = max(f, hoy)  # lo ya vencido cuenta desde hoy
            c, p = vencimientos.get(f, (0.0, 0.0))
            vencimientos[f] = (c + float(cob or 0), p + float(pag or 0))
        recurrentes = self.env["apunts.dat.pago"].sudo().fechas(hoy, hoy + timedelta(days=DAT_HORIZONTE))

        saldo = tesoreria
        dias = None
        lineas = []
        d = hoy
        while d <= hoy + timedelta(days=DAT_HORIZONTE):
            cob, pag = vencimientos.get(d, (0.0, 0.0))
            rec = recurrentes.get(d, 0.0)
            saldo += cob - pag - rec
            if con_proyeccion:
                lineas.append({"fecha": d, "cobros": cob, "pagos": pag,
                               "recurrentes": rec, "saldo": saldo})
            if saldo <= 0 and dias is None and d > hoy:
                dias = (d - hoy).days
            d += timedelta(days=1)
        if dias is None:
            dias = DAT_HORIZONTE
        return (dias, lineas) if con_proyeccion else dias

    # ══ Cálculo de todos los KPIs de una semana ══════════════════════════════

    def _valores_semana(self, lunes, es_actual=False):
        """Devuelve {clave: valor} para la semana que empieza ese lunes.

        `es_actual`: la semana en curso (o la que se está cerrando ahora mismo)
        calcula las fotos en vivo; una semana pasada las recupera de las fotos
        diarias del panel."""
        domingo = lunes + timedelta(days=6)
        fin_dt = domingo + timedelta(days=1)
        hoy = fields.Date.context_today(self)
        corte = min(domingo, hoy)
        ini_ano = date(domingo.year, 1, 1)
        # Los FLUJOS de la semana se acotan al año natural: la semana 1 empieza
        # a finales de diciembre y, si no, arrastraría los asientos de apertura
        # del 31/12 (que llevan las ventas de todo el año anterior en las 70x).
        ini_flujo = max(lunes, ini_ano)
        fin_flujo = min(domingo, date(domingo.year, 12, 31))
        fin_flujo_dt = fin_flujo + timedelta(days=1)
        cid = self._cid()
        v = {}

        # ── Bloque 1 · Actividad comercial ───────────────────────────────────
        # Facturación = ingresos por ventas contabilizados (70x): la misma
        # cifra que el P&G, el Tablero y el Análisis de ventas
        v["fact_semana"] = self._num("""
            SELECT COALESCE(SUM(-aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aa.code_store->>%s LIKE '70%%' AND aml.date >= %s AND aml.date <= %s""",
            (cid, str(cid), ini_flujo, fin_flujo))
        v["pedidos_semana"] = self._num("""
            SELECT COALESCE(SUM(amount_untaxed), 0) FROM sale_order
            WHERE state IN ('sale', 'done') AND company_id = %s
              AND date_order >= %s AND date_order < %s""", (cid, ini_flujo, fin_flujo_dt))
        fact_ytd = self._num("""
            SELECT COALESCE(SUM(-aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aa.code_store->>%s LIKE '70%%' AND aml.date >= %s AND aml.date <= %s""", (cid, str(cid), ini_ano, corte))
        dias_prod = self._dias_productivos(ini_ano, corte)
        if es_actual:
            v["cartera_pendiente"] = self._num("""
                SELECT COALESCE(SUM((sol.product_uom_qty - sol.qty_delivered) * sol.price_unit
                                    * (1 - COALESCE(sol.discount, 0) / 100.0)), 0)
                FROM sale_order_line sol JOIN sale_order so ON so.id = sol.order_id
                WHERE so.state IN ('sale', 'done') AND sol.display_type IS NULL
                  AND sol.product_uom_qty > sol.qty_delivered""")
        else:
            # Semana pasada: la cartera a cierre de esa semana (domingo), igual
            # para todas las semanas y comparable entre ellas
            v["cartera_pendiente"] = self._cartera_asof(fin_dt)
        ritmo_dia = self._div(fact_ytd, dias_prod)
        v["cdc"] = (self._div(v["cartera_pendiente"], ritmo_dia)
                    if v["cartera_pendiente"] is not None and ritmo_dia else None)

        # ── Bloques 2 y 3 · Rentabilidad y costes (acumulado del año) ────────
        c = self._cascada(ini_ano, corte)
        ventas = c["fact"]
        v["ebitda"] = self._div(c["ebitda"], ventas, 100.0)
        v["margen_neto"] = self._div(c["resultado"], ventas, 100.0)
        v["amortizaciones_pct"] = self._div(c["amortizaciones"], ventas, 100.0)
        v["financieros_pct"] = self._div(c["financieros"], ventas, 100.0)
        v["variables_pct"] = self._div(c["variables_directos"], ventas, 100.0)
        v["semivariables_pct"] = self._div(c["semivariables"], ventas, 100.0)
        v["fijos_pct"] = self._div(c["fijos_operativos"], ventas, 100.0)
        v["cov"] = self._div(c["variables_directos"] + c["semivariables"] + c["fijos_operativos"],
                             ventas, 100.0)
        v["edv"] = self._div(c["estructura"], ventas, 100.0)

        # ── Bloque 4 · Tesorería y circulante (foto del balance al cierre) ───
        b = self._balance_asof(corte)
        v["tesoreria_eur"] = b["tesoreria"]
        v["cobros_pendientes"] = b["clientes"]
        v["liquidez"] = self._div(b["activo_c"], b["pasivo_c"])
        v["liq_inmediata"] = self._div(b["activo_c"] - b["existencias"], b["pasivo_c"])
        v["tesoreria"] = self._div(b["tesoreria"], b["pasivo_c"])
        v["solvencia"] = self._div(b["activo_t"], b["pasivo_t"])
        v["endeudamiento"] = self._div(b["pasivo_t"], b["activo_t"], 100.0)
        v["roe"] = self._div(c["resultado"], b["patrimonio"], 100.0) if b["patrimonio"] > 0 else None
        v["roa"] = self._div(c["resultado"], b["activo_t"], 100.0)
        # Periodos medios con saldo MEDIO (inicio de año y cierre), como pide el cuadro
        b0 = self._balance_asof(ini_ano - timedelta(days=1))
        dias_ano = (corte - ini_ano).days + 1
        clientes_medio = (b0["clientes"] + b["clientes"]) / 2.0
        proveedores_medio = (b0["proveedores"] + b["proveedores"]) / 2.0
        v["pmc"] = self._div(clientes_medio, ventas, dias_ano) if ventas > 0 else None
        v["pmp"] = self._div(proveedores_medio, c["compras"], dias_ano) if c["compras"] > 0 else None
        v["dat"] = float(self._dat(corte))  # a la fecha de corte: se reconstruye hacia atrás

        # ── Bloque 5 · Producción (solo ESA semana) ──────────────────────────
        # Solo OT comparables: con tiempo previsto, con horas reales, y cerradas
        # como mucho una semana después de su último fichaje. Una OT que se
        # cierra meses después de trabajarse (cierre administrativo) contaría
        # todas sus horas en la semana del cierre y hundiría la eficiencia.
        prev, real, n_ot = self._uno("""
            SELECT COALESCE(SUM(wo.duration_expected), 0) / 60.0,
                   COALESCE(SUM(wo.duration), 0) / 60.0, COUNT(*)
            FROM mrp_workorder wo
            LEFT JOIN (SELECT workorder_id, MAX(date_end) AS ultimo
                       FROM mrp_workcenter_productivity
                       WHERE date_end IS NOT NULL GROUP BY workorder_id) u
                   ON u.workorder_id = wo.id
            WHERE wo.state = 'done' AND wo.date_finished >= %s AND wo.date_finished < %s
              AND wo.duration_expected > 0 AND wo.duration > 0
              AND (u.ultimo IS NULL OR wo.date_finished - u.ultimo <= INTERVAL '7 days')""",
            (lunes, fin_dt)) or (0, 0, 0)
        prev, real = float(prev or 0), float(real or 0)
        v["eficiencia"] = self._div(prev, real, 100.0) if real else None
        v["desviacion_of"] = self._div(prev - real, prev, 100.0) if prev else None
        h_maquina = self._num("""
            SELECT COALESCE(SUM(duration), 0) / 60.0 FROM mrp_workcenter_productivity
            WHERE date_end IS NOT NULL AND date_end >= %s AND date_end < %s""", (lunes, fin_dt))
        # MACPRE = toda la plantilla: horas en OF ÷ presencia fichada (oficina
        # incluida). MACOP = solo los operarios de planta («Operario de planta»
        # en la ficha): horas máquina ÷ horas de operario en OF. Así se ve si
        # las horas de planta cubren la presencia global (criterio JR, 21/09/2026).
        h_oper_todos = self._horas_union(lunes, fin_dt, solo_planta=False)
        h_oper_planta = self._horas_union(lunes, fin_dt, solo_planta=True)
        presencia_todos = self._num("""
            SELECT COALESCE(SUM(a.worked_hours), 0) FROM hr_attendance a
            WHERE a.check_out IS NOT NULL AND a.worked_hours <= 16
              AND a.check_in >= %s AND a.check_in < %s""", (lunes, fin_dt))
        v["macpre"] = self._div(h_oper_todos, presencia_todos, 100.0) if presencia_todos else None
        v["macop"] = self._div(h_maquina, h_oper_planta) if h_oper_planta else None
        if es_actual:
            try:
                v["wip_valor"] = float(
                    self.env["apunts.direccion.resumen"].sudo().create({}).wip_valor or 0.0)
            except Exception as e:
                _logger.warning("KPI wip_valor: %s", e)
                v["wip_valor"] = None
        else:
            v["wip_valor"] = self._foto_panel_arrastrada("wip_valor", lunes, domingo)

        # ── Bloque 6 · Servicio y calidad (solo ESA semana) ──────────────────
        ok, tot = self._uno("""
            SELECT COUNT(*) FILTER (WHERE sp.date_done::date <= so.commitment_date::date), COUNT(*)
            FROM stock_picking sp
            JOIN stock_picking_type t ON t.id = sp.picking_type_id
            JOIN sale_order so ON so.id = sp.sale_id
            WHERE t.code = 'outgoing' AND sp.state = 'done'
              AND sp.date_done >= %s AND sp.date_done < %s
              AND so.commitment_date IS NOT NULL""", (lunes, fin_dt)) or (0, 0)
        v["entregas_fecha"] = self._div(float(ok or 0), float(tot or 0), 100.0) if tot else None
        tcp, n_alb = self._uno("""
            SELECT AVG(sp.date_done::date - so.date_order::date), COUNT(*)
            FROM stock_picking sp
            JOIN stock_picking_type t ON t.id = sp.picking_type_id
            JOIN sale_order so ON so.id = sp.sale_id
            WHERE t.code = 'outgoing' AND sp.state = 'done'
              AND sp.date_done >= %s AND sp.date_done < %s""", (lunes, fin_dt)) or (None, 0)
        v["tcp"] = float(tcp) if n_alb and tcp is not None else None
        # Horas de retrabajo: fichajes en las fases de retrabajo que abre el
        # supervisor al rectificar piezas (módulo lira_mfg_supervisor).
        self.env.cr.execute("SELECT to_regclass('lira_refab_wo_rel')")
        if self.env.cr.fetchone()[0]:
            h_retrabajo = self._num("""
                SELECT COALESCE(SUM(p.duration), 0) / 60.0 FROM mrp_workcenter_productivity p
                WHERE p.workorder_id IN (SELECT wo_id FROM lira_refab_wo_rel)
                  AND p.date_end IS NOT NULL AND p.date_end >= %s AND p.date_end < %s""",
                (lunes, fin_dt))
            v["retrabajo"] = self._div(h_retrabajo, h_maquina, 100.0) if h_maquina else None
        else:
            v["retrabajo"] = None
        return v

    # ══ Persistencia semanal ═════════════════════════════════════════════════

    def _guardar_semana(self, lunes, valores, cerrar, reconstruido=False):
        """Escribe (o actualiza) las filas de la semana. Nunca toca una semana
        ya cerrada: el dato de la reunión del lunes no cambia después."""
        Semana = self.env["apunts.kpi.semana"].sudo().with_context(apunts_kpi_forzar=True)
        Criterio = self.env["lira.ratio.criterio"].sudo()
        kpis = self.env["apunts.kpi"].sudo().search([("activo", "=", True)])
        iso = lunes.isocalendar()
        domingo = lunes + timedelta(days=6)
        n = 0
        for kpi in kpis:
            if kpi.fiable_desde and domingo < kpi.fiable_desde:
                continue
            valor = valores.get(kpi.clave)
            if valor is None:
                continue
            existente = Semana.search([("kpi_id", "=", kpi.id), ("fecha", "=", lunes)], limit=1)
            if existente and existente.cerrada:
                continue
            verde, _amarillo, _sentido = Criterio.criterio(kpi.clave)
            vals = {
                "kpi_id": kpi.id, "clave": kpi.clave, "fecha": lunes,
                "semana": iso[1], "anio": iso[0], "valor": valor,
                "objetivo": verde if verde is not None else 0.0,
                "estado": Criterio.evaluar(kpi.clave, valor, valores),
                "cerrada": cerrar, "reconstruido": reconstruido,
                "fecha_cierre": fields.Datetime.now() if cerrar else False,
            }
            if existente:
                existente.write(vals)
            else:
                Semana.create(vals)
            n += 1
        return n

    @api.model
    def actualizar_actual(self):
        """La semana en curso, con los datos de hoy (se muestra como 'actual')."""
        hoy = fields.Date.context_today(self)
        lunes = self._lunes_de(hoy)
        valores = self._valores_semana(lunes, es_actual=True)
        n = self._guardar_semana(lunes, valores, cerrar=False)
        self.env["apunts.kpi.serie"].sudo()._regenerar_todo()
        return n

    @api.model
    def cerrar_semana(self, lunes=None):
        """Cierra la semana anterior con los datos del cierre del domingo.
        Se llama el lunes de madrugada; las fotos se toman en vivo."""
        hoy = fields.Date.context_today(self)
        lunes = lunes or (self._lunes_de(hoy) - timedelta(days=7))
        valores = self._valores_semana(lunes, es_actual=True)
        n = self._guardar_semana(lunes, valores, cerrar=True)
        self.env["apunts.kpi.serie"].sudo()._regenerar_todo()
        _logger.info("KPIs Dirección: semana %s cerrada (%s valores).", lunes, n)
        return n

    @api.model
    def reconstruir_historico(self, desde=None):
        """Rehace las semanas cerradas del año que aún no existen, con lo que
        hay en Odoo. Las semanas ya cerradas no se tocan."""
        hoy = fields.Date.context_today(self)
        lunes = desde or PRIMER_LUNES
        lunes_actual = self._lunes_de(hoy)
        n = 0
        while lunes < lunes_actual:
            valores = self._valores_semana(lunes, es_actual=False)
            n += self._guardar_semana(lunes, valores, cerrar=True, reconstruido=True)
            lunes += timedelta(days=7)
        # y la semana en curso
        valores = self._valores_semana(lunes_actual, es_actual=True)
        n += self._guardar_semana(lunes_actual, valores, cerrar=False)
        self.env["apunts.kpi.serie"].sudo()._regenerar_todo()
        _logger.info("KPIs Dirección: histórico reconstruido (%s valores).", n)
        return n

    @api.model
    def cron_actualizar_actual(self):
        self.actualizar_actual()

    @api.model
    def cron_cerrar_semana(self):
        self.cerrar_semana()
        self.actualizar_actual()
