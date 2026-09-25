"""Registro semanal del cuadro de mando (el CMI de siempre).

Replica la hoja "registro semanal" + "operaciones" del cuadro que la empresa
llevaba en Excel: una fila por semana con los datos del negocio y las columnas
calculadas (liquidez en varios niveles, producción económica, ventas semanal,
producción material, compras y previsión de pagos), más los mínimos y objetivos
con los que se comparaba cada indicador.

Casi todo se reconstruye hacia atrás desde la contabilidad y el almacén, así que
al instalar ya hay histórico de verdad. Lo único que no se puede recuperar del
pasado son las fotos de un instante (el dinero metido en el taller y el stock
comprometido): esos se van guardando a partir de ahora.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApuntsCmiSemana(models.Model):
    _name = "apunts.cmi.semana"
    _description = "Registro semanal del cuadro de mando (CMI)"
    _order = "fecha_ini desc"
    _rec_name = "display_name"

    # ── Identificación de la semana ───────────────────────────────────────────
    fecha_ini = fields.Date(string="Semana (lunes)", required=True, index=True)
    fecha_fin = fields.Date(string="Hasta (domingo)")
    semana = fields.Integer(string="Nº semana", index=True)
    anio = fields.Integer(string="Año", index=True)

    # ── Datos del negocio ─────────────────────────────────────────────────────
    saldo_bancos = fields.Float(string="Saldo en bancos", digits=(16, 2))
    cobros_cartera = fields.Float(string="Cobros en cartera", digits=(16, 2),
                                  help="Giros, confirming y pagarés pendientes de vencer.")
    cobros_pendientes = fields.Float(string="Cobros pendientes", digits=(16, 2),
                                     help="Facturas de cliente emitidas y aún no cobradas.")
    facturacion = fields.Float(string="Facturación", digits=(16, 2),
                               help="Facturado en la semana, sin IVA.")
    albaranes_cliente = fields.Float(string="Albaranes de cliente", digits=(16, 2),
                                     help="Valor de lo entregado en la semana y todavía sin facturar.")
    stock_ventas = fields.Float(string="Stock vendido", digits=(16, 2))
    encurso = fields.Float(string="En curso (taller)", digits=(16, 2))
    stock_sin_pedido = fields.Float(string="Stock sin pedido", digits=(16, 2))
    pedidos_totales = fields.Float(string="Cartera de pedidos", digits=(16, 2),
                                   help="Vendido y pendiente de entregar al cierre de la semana.")
    pedidos_3m = fields.Float(string="Pedidos pendientes 3 meses", digits=(16, 2))
    pedidos_6m = fields.Float(string="Pedidos pendientes 6 meses", digits=(16, 2))
    facturas_proveedor = fields.Float(string="Facturas de proveedor", digits=(16, 2))
    pedidos_proveedor = fields.Float(string="Pedidos a proveedor", digits=(16, 2))
    albaranes_proveedor = fields.Float(string="Albaranes de proveedor", digits=(16, 2))
    iva = fields.Float(string="IVA", digits=(16, 2))
    irpf = fields.Float(string="IRPF", digits=(16, 2))
    seguridad_social = fields.Float(string="Seguridad Social", digits=(16, 2))
    pagos_pendientes = fields.Float(string="Pagos pendientes", digits=(16, 2),
                                    help="Facturas de proveedor emitidas y aún no pagadas.")
    albaranes_sin_facturar = fields.Float(string="Albaranes sin facturar", digits=(16, 2),
                                          help="Entregado al cliente y todavía sin factura.")

    # ── Columnas calculadas (las de la hoja "operaciones") ────────────────────
    cobros_mas_cartera = fields.Float(string="Cobros pend. + cartera", compute="_compute_operaciones",
                                      store=True, digits=(16, 2),
                                      help="Columna C del cuadro de siempre: lo pendiente de cobrar "
                                           "más los efectos en cartera.")
    sumatorio_pagos = fields.Float(string="Sumatorio de pagos", compute="_compute_operaciones",
                                   store=True, digits=(16, 2),
                                   help="Columna O de operaciones: proveedores + pedidos + albaranes "
                                        "de proveedor + IVA + IRPF + Seguridad Social.")
    liquidez_bancos = fields.Float(string="Liquidez sin financiación", compute="_compute_operaciones",
                                   store=True, digits=(16, 2), help="Saldo en bancos.")
    liquidez_cartera = fields.Float(string="Liquidez + cartera", compute="_compute_operaciones",
                                    store=True, digits=(16, 2), help="Saldo en bancos + cobros en cartera.")
    liquidez_actividad = fields.Float(string="Liquidez incluyendo actividad", compute="_compute_operaciones",
                                      store=True, digits=(16, 2),
                                      help="Saldo en bancos + cobros en cartera + cobros pendientes.")
    liquidez_pedidos = fields.Float(string="Liquidez + pedidos en marcha", compute="_compute_operaciones",
                                    store=True, digits=(16, 2),
                                    help="Lo anterior más la cartera de pedidos.")
    cobros_menos_pagos = fields.Float(string="Cobros − pagos", compute="_compute_operaciones",
                                      store=True, digits=(16, 2),
                                      help="Saldo + cobros en cartera + cobros pendientes − pagos pendientes.")
    cartera_menos_pagos = fields.Float(string="Cartera − pagos", compute="_compute_operaciones",
                                       store=True, digits=(16, 2))
    produccion_economica = fields.Float(string="Producción económica", compute="_compute_operaciones",
                                        store=True, digits=(16, 2), help="Facturación + albaranes.")
    ventas_semanal = fields.Float(string="Ventas de la semana", compute="_compute_operaciones",
                                  store=True, digits=(16, 2),
                                  help="Facturación + albaranes + lo que ha crecido la cartera de pedidos.")
    produccion_material = fields.Float(string="Producción material", compute="_compute_operaciones",
                                       store=True, digits=(16, 2),
                                       help="Lo que ha salido del taller: facturación + albaranes menos los de la "
                                            "semana anterior, más lo que ha variado el stock vendido y el en curso.")
    compras_semanal = fields.Float(string="Compras de la semana", compute="_compute_operaciones",
                                   store=True, digits=(16, 2),
                                   help="Facturas + pedidos + albaranes de proveedor.")
    prevision_pagos = fields.Float(string="Previsión de pagos", compute="_compute_operaciones",
                                   store=True, digits=(16, 2), help="Seguridad Social + IRPF + IVA.")
    encurso_mas_stock = fields.Float(string="En curso + stock", compute="_compute_operaciones",
                                     store=True, digits=(16, 2))
    # Bloque de ejecución de la cartera (columnas AD..AL de la hoja "operaciones")
    resto_pedidos = fields.Float(string="Resto de pedidos pendientes", compute="_compute_operaciones",
                                 store=True, digits=(16, 2),
                                 help="Cartera pendiente que vence más allá de 3 meses.")
    cantidad_ejecutada = fields.Float(string="Cantidad ejecutada", compute="_compute_operaciones",
                                      store=True, digits=(16, 2),
                                      help="Trabajo ya hecho de la cartera: en curso + stock vendido + albaranes.")
    pct_ejecutado_total = fields.Float(string="% ejecutado (total)", compute="_compute_operaciones",
                                       store=True, digits=(16, 1),
                                       help="Cantidad ejecutada sobre toda la cartera pendiente.")
    pct_ejecutado_3m = fields.Float(string="% ejecutado (3 meses)", compute="_compute_operaciones",
                                    store=True, digits=(16, 1),
                                    help="Cantidad ejecutada sobre la cartera que vence en 3 meses.")

    # ── Semáforos contra los mínimos/objetivos del cuadro ─────────────────────
    ok_saldo = fields.Boolean(string="Saldo OK", compute="_compute_operaciones", store=True)
    ok_cartera = fields.Boolean(string="Cartera OK", compute="_compute_operaciones", store=True)
    ok_facturacion = fields.Boolean(string="Facturación OK", compute="_compute_operaciones", store=True)
    ok_produccion = fields.Boolean(string="Producción OK", compute="_compute_operaciones", store=True)

    reconstruido = fields.Boolean(
        string="Reconstruido", default=False,
        help="Semana calculada hacia atrás desde la contabilidad. Los datos de foto "
             "(en curso del taller y stock) no se pueden recuperar del pasado y salen a cero.",
    )

    _sql_constraints = [
        ("semana_uniq", "unique(fecha_ini)", "Ya existe el registro de esa semana."),
    ]

    @api.depends("fecha_ini", "semana", "anio")
    def _compute_display_name(self):
        for r in self:
            r.display_name = "S%02d/%s" % (r.semana or 0, r.anio or "")

    # ── Mínimos y objetivos (los del cuadro de siempre, configurables) ────────

    def _objetivos(self):
        ICP = self.env["ir.config_parameter"].sudo()
        def p(clave, defecto):
            try:
                return float(ICP.get_param("apunts_cmi.%s" % clave, defecto))
            except (TypeError, ValueError):
                return float(defecto)
        return {
            "saldo_min": p("min_saldo_bancos", 130000),
            "cartera_min": p("min_cartera_pedidos", 400000),
            "facturacion_min": p("obj_facturacion_semana", 40000),
            "produccion_min": p("obj_produccion_material", 40000),
            "stock_max": p("max_stock_vendido", 75000),
            "stock_min": p("min_stock_vendido", 45000),
            "liquidez_3m": p("min_liquidez_3meses", 45000),
            "compras_max": p("max_compras_proveedor", 35000),
            "encurso_min": p("min_encurso_stock", 90000),
            "encurso_max": p("max_encurso_stock", 135000),
        }

    @api.depends("saldo_bancos", "cobros_cartera", "cobros_pendientes", "facturacion",
                 "albaranes_cliente", "stock_ventas", "encurso", "pedidos_totales",
                 "facturas_proveedor", "pedidos_proveedor", "albaranes_proveedor",
                 "iva", "irpf", "seguridad_social", "pagos_pendientes", "stock_sin_pedido")
    def _compute_operaciones(self):
        obj = self._objetivos()
        for r in self:
            ant = r._semana_anterior()
            r.cobros_mas_cartera = r.cobros_pendientes + r.cobros_cartera
            # Columna O del Excel: el sumatorio de todos los pagos de la semana
            r.sumatorio_pagos = (r.facturas_proveedor + r.pedidos_proveedor
                                 + r.albaranes_proveedor + r.iva + r.irpf
                                 + r.seguridad_social)
            r.liquidez_bancos = r.saldo_bancos
            r.liquidez_cartera = r.saldo_bancos + r.cobros_cartera
            r.liquidez_actividad = r.saldo_bancos + r.cobros_cartera + r.cobros_pendientes
            # El Excel suma aquí la cartera a 3 MESES (columna M), no la total
            r.liquidez_pedidos = r.liquidez_actividad + r.pedidos_3m
            r.cobros_menos_pagos = r.liquidez_actividad - r.sumatorio_pagos
            r.cartera_menos_pagos = r.liquidez_pedidos - r.sumatorio_pagos
            r.produccion_economica = r.facturacion + r.albaranes_cliente
            # Ventas = producción económica + lo que ha crecido la cartera
            # Excel J: facturación + albaranes + lo que ha crecido la cartera A 3 MESES
            r.ventas_semanal = r.produccion_economica + (
                r.pedidos_3m - (ant.pedidos_3m if ant else 0.0))
            # Producción material: lo que de verdad ha salido del taller
            r.produccion_material = (
                r.facturacion + r.albaranes_cliente
                - (ant.albaranes_cliente if ant else 0.0)
                + r.stock_ventas - (ant.stock_ventas if ant else 0.0)
                + r.encurso - (ant.encurso if ant else 0.0)
            )
            r.compras_semanal = r.facturas_proveedor + r.pedidos_proveedor + r.albaranes_proveedor
            r.prevision_pagos = r.seguridad_social + r.irpf + r.iva
            r.encurso_mas_stock = r.encurso + r.stock_ventas + r.stock_sin_pedido
            # Ejecución de la cartera: cuánto del trabajo contratado ya está hecho
            r.resto_pedidos = r.pedidos_totales - r.pedidos_3m
            r.cantidad_ejecutada = r.encurso + r.stock_ventas + r.albaranes_sin_facturar
            r.pct_ejecutado_total = (
                r.cantidad_ejecutada / r.pedidos_totales * 100.0) if r.pedidos_totales else 0.0
            r.pct_ejecutado_3m = (
                r.cantidad_ejecutada / r.pedidos_3m * 100.0) if r.pedidos_3m else 0.0
            r.ok_saldo = r.saldo_bancos >= obj["saldo_min"]
            r.ok_cartera = r.pedidos_totales >= obj["cartera_min"]
            r.ok_facturacion = r.facturacion >= obj["facturacion_min"]
            r.ok_produccion = r.produccion_material >= obj["produccion_min"]

    def _semana_anterior(self):
        self.ensure_one()
        if not self.fecha_ini:
            return False
        return self.search([("fecha_ini", "=", self.fecha_ini - timedelta(days=7))], limit=1)

    # ── Cálculo de una semana con los datos reales de Odoo ────────────────────

    def _sql(self, query, params=()):
        self.env.cr.execute(query, params)
        row = self.env.cr.fetchone()
        return float(row[0] or 0.0) if row else 0.0

    @api.model
    def _datos_de_la_semana(self, lunes, es_semana_actual=False):
        """Devuelve los datos del negocio de esa semana.

        Los FLUJOS (facturación, albaranes, compras) se suman por fecha, así que
        se pueden reconstruir de semanas pasadas. Los SALDOS (bancos, cobros,
        impuestos) se calculan a cierre de la semana, también hacia atrás. Lo
        único que no se puede recuperar del pasado es la foto del taller (dinero
        en curso) y del almacén: eso solo vale para la semana en curso."""
        domingo = lunes + timedelta(days=6)
        cid = self.env.company.id
        # Flujos acotados al año natural (la semana 1 empieza en diciembre y
        # arrastraría los asientos de apertura del 31/12)
        ini_f = max(lunes, date(domingo.year, 1, 1))
        fin_f = min(domingo, date(domingo.year, 12, 31))
        v = {}

        # Facturación de la semana: ingresos por ventas contabilizados (70x),
        # la misma cifra que el P&G y el Tablero
        v["facturacion"] = self._sql("""
            SELECT COALESCE(SUM(-aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aa.code_store->>%s LIKE '70%%' AND aml.date >= %s AND aml.date <= %s""", (cid, str(cid), ini_f, fin_f))

        # Entregado al cliente en la semana (albaranes de salida validados)
        v["albaranes_cliente"] = self._sql("""
            SELECT COALESCE(SUM(sp.total_value), 0)
            FROM stock_picking sp JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
            WHERE spt.code='outgoing' AND sp.state='done'
              AND sp.date_done >= %s AND sp.date_done < %s""",
            (lunes, domingo + timedelta(days=1)))

        # Saldo de bancos y caja al cierre de la semana
        v["saldo_bancos"] = self._sql("""
            SELECT COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aa.account_type='asset_cash' AND aml.parent_state='posted'
              AND aml.company_id=%s AND aml.date <= %s""", (cid, domingo))

        # Facturas de cliente emitidas hasta esa fecha y no cobradas a día de hoy
        v["cobros_pendientes"] = self._sql("""
            SELECT COALESCE(SUM(amount_residual_signed), 0) FROM account_move
            WHERE move_type IN ('out_invoice','out_refund') AND state='posted'
              AND company_id=%s AND date <= %s
              AND payment_state IN ('not_paid','partial')""", (cid, domingo))

        # Deuda con proveedores y pagos pendientes
        v["pagos_pendientes"] = abs(self._sql("""
            SELECT COALESCE(SUM(amount_residual_signed), 0) FROM account_move
            WHERE move_type IN ('in_invoice','in_refund') AND state='posted'
              AND company_id=%s AND date <= %s
              AND payment_state IN ('not_paid','partial')""", (cid, domingo)))

        # Compras de la semana
        v["facturas_proveedor"] = abs(self._sql("""
            SELECT COALESCE(SUM(amount_untaxed_signed), 0) FROM account_move
            WHERE move_type IN ('in_invoice','in_refund') AND state='posted'
              AND company_id=%s AND date >= %s AND date <= %s""", (cid, ini_f, fin_f)))
        v["pedidos_proveedor"] = self._sql("""
            SELECT COALESCE(SUM(amount_untaxed), 0) FROM purchase_order
            WHERE state IN ('purchase','done') AND company_id=%s
              AND date_order >= %s AND date_order < %s""",
            (cid, lunes, domingo + timedelta(days=1)))
        v["albaranes_proveedor"] = self._sql("""
            SELECT COALESCE(SUM(sp.total_value), 0)
            FROM stock_picking sp JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
            WHERE spt.code='incoming' AND sp.state='done'
              AND sp.date_done >= %s AND sp.date_done < %s""",
            (lunes, domingo + timedelta(days=1)))

        # Impuestos al cierre de la semana
        v["iva"] = abs(self._sql("""
            SELECT COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state='posted' AND aml.company_id=%s AND aml.date <= %s
              AND aa.code_store->>%s LIKE '477%%'""", (cid, domingo, str(cid))))
        v["irpf"] = abs(self._sql("""
            SELECT COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state='posted' AND aml.company_id=%s AND aml.date <= %s
              AND aa.code_store->>%s LIKE '4751%%'""", (cid, domingo, str(cid))))
        v["seguridad_social"] = abs(self._sql("""
            SELECT COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state='posted' AND aml.company_id=%s AND aml.date <= %s
              AND aa.code_store->>%s LIKE '476%%'""", (cid, domingo, str(cid))))

        # Entregado al cliente y todavía sin facturar (columna I de "operaciones"
        # y base del albarán pendiente): líneas de venta con más entregado que
        # facturado, valoradas a precio de línea.
        v["albaranes_sin_facturar"] = self._sql("""
            SELECT COALESCE(SUM((sol.qty_delivered - sol.qty_invoiced) * sol.price_unit
                                * (1 - COALESCE(sol.discount,0)/100.0)), 0)
            FROM sale_order_line sol JOIN sale_order so ON so.id = sol.order_id
            WHERE so.state IN ('sale','done') AND sol.display_type IS NULL
              AND sol.qty_delivered > sol.qty_invoiced""")

        # Cartera de pedidos: vendido y pendiente de entregar. Solo tiene sentido
        # a día de hoy (Odoo no guarda cuánto quedaba por servir en el pasado).
        if es_semana_actual:
            v["pedidos_totales"] = self._sql("""
                SELECT COALESCE(SUM((sol.product_uom_qty - sol.qty_delivered) * sol.price_unit
                                    * (1 - COALESCE(sol.discount,0)/100.0)), 0)
                FROM sale_order_line sol JOIN sale_order so ON so.id = sol.order_id
                WHERE so.state IN ('sale','done') AND sol.display_type IS NULL
                  AND sol.product_uom_qty > sol.qty_delivered""")
            for campo, meses in (("pedidos_3m", 3), ("pedidos_6m", 6)):
                v[campo] = self._sql("""
                    SELECT COALESCE(SUM((sol.product_uom_qty - sol.qty_delivered) * sol.price_unit
                                        * (1 - COALESCE(sol.discount,0)/100.0)), 0)
                    FROM sale_order_line sol JOIN sale_order so ON so.id = sol.order_id
                    WHERE so.state IN ('sale','done') AND sol.display_type IS NULL
                      AND sol.product_uom_qty > sol.qty_delivered
                      AND so.commitment_date <= %s""",
                    (domingo + timedelta(days=30 * meses),))
            # Foto del taller y del almacén
            try:
                wip = self.env["mrp.production"].sudo().search([("apunts_is_wip", "=", True)])
                v["encurso"] = sum(wip.mapped("apunts_cost_total_real"))
            except Exception:
                v["encurso"] = 0.0
            v["stock_ventas"] = self._sql(
                "SELECT COALESCE(SUM(remaining_value),0) FROM stock_valuation_layer WHERE company_id=%s",
                (cid,))
            # Stock sin pedido: la parte del almacén NO reservada para ningún
            # pedido, valorada al coste medio de cada producto.
            v["stock_sin_pedido"] = self._sql("""
                SELECT COALESCE(SUM(GREATEST(sq.quantity - sq.reserved_quantity, 0)
                       * COALESCE(svl.coste_unit, 0)), 0)
                FROM stock_quant sq
                JOIN stock_location sl ON sl.id = sq.location_id AND sl.usage = 'internal'
                LEFT JOIN LATERAL (
                    SELECT CASE WHEN SUM(remaining_qty) > 0
                                THEN SUM(remaining_value)/SUM(remaining_qty) ELSE 0 END AS coste_unit
                    FROM stock_valuation_layer v2
                    WHERE v2.product_id = sq.product_id AND v2.company_id = %s
                ) svl ON TRUE""", (cid,))
        return v

    @api.model
    def actualizar_semana(self, lunes=None):
        """Calcula (o recalcula) la semana indicada. Sin fecha, la de hoy."""
        hoy = fields.Date.context_today(self)
        if not lunes:
            lunes = hoy - timedelta(days=hoy.weekday())
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        vals = self._datos_de_la_semana(lunes, es_semana_actual=(lunes == lunes_actual))
        iso = lunes.isocalendar()
        vals.update({
            "fecha_ini": lunes,
            "fecha_fin": lunes + timedelta(days=6),
            "semana": iso[1],
            "anio": iso[0],
            "reconstruido": lunes != lunes_actual,
        })
        rec = self.search([("fecha_ini", "=", lunes)], limit=1)
        if rec:
            rec.write(vals)
        else:
            rec = self.create(vals)
        return rec

    @api.model
    def reconstruir_historico(self, desde=None):
        """Rehace todas las semanas desde una fecha (por defecto, el 1 de enero
        del año en curso) con lo que ya hay en la contabilidad y el almacén."""
        hoy = fields.Date.context_today(self)
        if not desde:
            desde = date(hoy.year, 1, 1)
        lunes = desde - timedelta(days=desde.weekday())
        n = 0
        while lunes <= hoy:
            self.actualizar_semana(lunes)
            lunes += timedelta(days=7)
            n += 1
        _logger.info("CMI: %s semanas reconstruidas desde %s", n, desde)
        return n

    @api.model
    def cron_semana(self):
        """Cada lunes cierra la semana anterior y abre la nueva."""
        hoy = fields.Date.context_today(self)
        lunes = hoy - timedelta(days=hoy.weekday())
        self.actualizar_semana(lunes - timedelta(days=7))
        self.actualizar_semana(lunes)
