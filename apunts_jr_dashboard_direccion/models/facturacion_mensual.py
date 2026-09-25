"""Facturación por mes (facturas de cliente reales) — la gráfica que pide
dirección para la tarjeta 'Facturación'. Antes esa tarjeta enlazaba a la
'Evolución mensual' de lira, que en realidad son PEDIDOS (amount_untaxed de
sale.order); por eso se solapaba con la tarjeta de pedidos. Esto son FACTURAS
(ingresos por ventas contabilizados en las cuentas 70x, por fecha contable:
la misma cifra que el P&G y el Tablero)."""

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Nombres de mes en español: strftime("%b") depende del idioma del servidor y
# sacaba "Jan 2026" en la lista mientras la gráfica decía "enero 2026".
MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
         'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


class ApuntsFacturacionMensualLine(models.Model):
    _name = "apunts.facturacion.mensual.line"
    _description = "Línea de facturación por mes"
    _order = "mes_fecha"

    user_id = fields.Many2one("res.users", ondelete="cascade", index=True)
    mes = fields.Char("Mes")
    mes_fecha = fields.Date("Mes (fecha)")
    num_facturas = fields.Integer("Facturas")
    total_neto = fields.Float("Facturación (€)", digits=(16, 2))
    variacion_pct = fields.Float("Var. % vs mes ant.", digits=(16, 1))
    es_mejor_mes = fields.Boolean("Mejor mes")

    def action_open_source(self):
        """Abre las facturas de cliente del mes."""
        self.ensure_one()
        if not self.mes_fecha:
            return False
        dt_ini = self.mes_fecha
        dt_fin = dt_ini + relativedelta(months=1) - relativedelta(days=1)
        return {
            "type": "ir.actions.act_window",
            "name": f"Facturas de cliente — {self.mes}",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "=", "posted"),
                ("date", ">=", fields.Date.to_string(dt_ini)),
                ("date", "<=", fields.Date.to_string(dt_fin)),
            ],
            "target": "current",
        }


class ApuntsFacturacionMensual(models.TransientModel):
    _name = "apunts.facturacion.mensual"
    _description = "Facturación por mes"

    periodos = fields.Integer("Meses a mostrar", default=12)

    def _build_data(self):
        self.ensure_one()
        today = date.today()
        n = max(self.periodos or 12, 1)
        cid = self.env.company.id
        ini = (today - relativedelta(months=n - 1)).replace(day=1)
        self.env.cr.execute(
            """
            SELECT to_char(aml.date, 'YYYY-MM') AS ym,
                   COUNT(DISTINCT aml.move_id) AS num,
                   COALESCE(SUM(-aml.balance), 0) AS neto
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aa.code_store->>%s LIKE '70%%' AND aml.date >= %s
            GROUP BY ym
            """,
            (cid, str(cid), ini.strftime("%Y-%m-%d")),
        )
        by_ym = {r[0]: (int(r[1] or 0), float(r[2] or 0.0)) for r in self.env.cr.fetchall()}
        lines, prev = [], None
        for i in range(n - 1, -1, -1):
            mes_ini = (today - relativedelta(months=i)).replace(day=1)
            ym = mes_ini.strftime("%Y-%m")
            num, neto = by_ym.get(ym, (0, 0.0))
            var = round((neto - prev) / prev * 100, 1) if prev not in (None, 0) else 0.0
            prev = neto
            lines.append({
                "mes": "%s %d" % (MESES[mes_ini.month - 1], mes_ini.year),
                "mes_fecha": mes_ini,
                "num_facturas": num,
                "total_neto": round(neto, 2),
                "variacion_pct": var,
                "es_mejor_mes": False,
            })
        con_datos = [d for d in lines if d["total_neto"] > 0]
        if con_datos:
            mx = max(d["total_neto"] for d in con_datos)
            for d in lines:
                if d["total_neto"] == mx:
                    d["es_mejor_mes"] = True
                    break
        return lines

    def _store_lines(self):
        self.ensure_one()
        Line = self.env["apunts.facturacion.mensual.line"]
        Line.search([("user_id", "=", self.env.user.id)]).unlink()
        # Solo los meses que SE HAN FACTURADO (petición de dirección: no mostrar
        # los meses vacíos). La variación se calcula en _build_data sobre la
        # serie completa, así que sigue siendo correcta mes a mes.
        for d in self._build_data():
            if d["num_facturas"]:
                Line.create({**d, "user_id": self.env.user.id})

    @api.model
    def action_open(self):
        """Punto de entrada: recalcula y abre la gráfica de barras de
        facturación por mes (con lista de detalle)."""
        rec = self.create({})
        rec._store_lines()
        graph = self.env.ref("apunts_jr_dashboard_direccion.apunts_facturacion_mensual_graph")
        lista = self.env.ref("apunts_jr_dashboard_direccion.apunts_facturacion_mensual_list")
        return {
            "type": "ir.actions.act_window",
            "name": "Facturación por mes",
            "res_model": "apunts.facturacion.mensual.line",
            "view_mode": "graph,list",
            "views": [(graph.id, "graph"), (lista.id, "list")],
            "domain": [("user_id", "=", self.env.user.id)],
            "context": {"create": False, "delete": False, "edit": False},
            "target": "current",
        }
