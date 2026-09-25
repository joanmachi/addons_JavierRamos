# -*- coding: utf-8 -*-
"""Evolución de costes vs facturación, mes a mes.

Es la hoja "Evolucion Costes" del cuadro del asesor, pero rellenándose sola:
una fila por mes y bloque (facturación, variables directos, semivariables,
fijos operativos, estructura, amortizaciones, financieros, total y beneficio)
con el importe y su porcentaje sobre la facturación del mes.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
         'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

CONCEPTOS = [
    ("facturacion", "Facturación", 10),
    ("variables_directos", "Variables directos", 20),
    ("semivariables", "Semivariables", 30),
    ("fijos_operativos", "Fijos operativos", 40),
    ("estructura", "Estructura / Dirección", 50),
    ("amortizaciones", "Amortizaciones", 60),
    ("financieros", "Gastos financieros", 70),
    ("sin_clasificar", "Sin clasificar", 80),
    ("total_costes", "TOTAL COSTES", 90),
    ("beneficio", "BENEFICIO / PÉRDIDA", 100),
]


class LiraEvolucionCosteLine(models.Model):
    _name = "lira.evolucion.coste.line"
    _description = "Evolución de costes — línea mes/bloque"
    _order = "secuencia, mes_fecha"

    user_id = fields.Many2one("res.users", ondelete="cascade", index=True)
    mes_fecha = fields.Date(string="Mes")
    mes = fields.Char(string="Mes (nombre)")
    concepto = fields.Selection([(k, n) for k, n, _s in CONCEPTOS], string="Concepto", index=True)
    secuencia = fields.Integer(string="Orden")
    importe = fields.Float(string="Importe (€)", digits=(16, 2))
    pct = fields.Float(string="% s/ facturación", digits=(16, 1))
    var_mes = fields.Float(string="Var. % vs mes anterior", digits=(16, 1),
                           help="Cuánto ha subido o bajado este bloque respecto al mes anterior.")


class LiraEvolucionCoste(models.TransientModel):
    _name = "lira.evolucion.coste"
    _description = "Evolución de costes vs facturación"

    @api.model
    def _datos_mes(self, ini, fin):
        """Importe de cada bloque en el mes, desde la contabilidad."""
        mapa = self.env["lira.cuenta.bloque"].mapa()
        self.env.cr.execute("""
            SELECT aa.code_store->>%s AS code,
                   SUM(aml.debit - aml.credit) AS neto
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aml.date >= %s AND aml.date <= %s
              AND (aa.code_store->>%s LIKE '6%%' OR aa.code_store->>%s LIKE '7%%')
            GROUP BY 1""",
            (str(self.env.company.id), self.env.company.id, ini, fin,
             str(self.env.company.id), str(self.env.company.id)))
        tot = {k: 0.0 for k, _n, _s in CONCEPTOS}
        for code, neto in self.env.cr.fetchall():
            code = code or ""
            neto = float(neto or 0.0)
            if code.startswith("70"):
                tot["facturacion"] += -neto          # ingresos: crédito positivo
            elif code.startswith("7"):
                continue                              # otros ingresos/variación: fuera de la hoja
            elif code in mapa:
                tot[mapa[code]] += neto
            elif code.startswith("68"):
                tot["amortizaciones"] += neto
            elif code.startswith("66"):
                tot["financieros"] += neto
            elif code.startswith("6"):
                tot["sin_clasificar"] += neto
        tot["total_costes"] = (tot["variables_directos"] + tot["semivariables"]
                               + tot["fijos_operativos"] + tot["estructura"]
                               + tot["amortizaciones"] + tot["financieros"]
                               + tot["sin_clasificar"])
        tot["beneficio"] = tot["facturacion"] - tot["total_costes"]
        return tot

    @api.model
    def action_open(self, date_from=None, date_to=None):
        """Genera la matriz mensual del rango pedido (por defecto, el año en
        curso hasta hoy) y la abre en tabla, lista y gráficas."""
        Line = self.env["lira.evolucion.coste.line"]
        Line.search([("user_id", "=", self.env.user.id)]).unlink()
        hoy = date.today()
        df = date_from or date(hoy.year, 1, 1)
        dt = date_to or hoy
        anterior = {}
        mes_ini = date(df.year, df.month, 1)
        while mes_ini <= dt:
            fin = min(mes_ini + relativedelta(months=1) - relativedelta(days=1), dt)
            tot = self._datos_mes(max(mes_ini, df), fin)
            fact = tot["facturacion"]
            for clave, _nombre, sec in CONCEPTOS:
                imp = tot[clave]
                if not imp and clave not in ("facturacion", "total_costes", "beneficio"):
                    anterior[clave] = imp
                    continue
                prev = anterior.get(clave)
                var = round((imp - prev) / abs(prev) * 100.0, 1) if prev else 0.0
                anterior[clave] = imp
                Line.create({
                    "user_id": self.env.user.id,
                    "mes_fecha": mes_ini,
                    "mes": "%s %d" % (MESES[mes_ini.month - 1], mes_ini.year),
                    "concepto": clave,
                    "secuencia": sec,
                    "importe": round(imp, 2),
                    "pct": round(imp / fact * 100.0, 1) if (fact and clave != "facturacion") else 0.0,
                    "var_mes": var,
                })
            mes_ini = mes_ini + relativedelta(months=1)
        pivot = self.env.ref("lira_dashboard_contabilidad.view_lira_evolucion_coste_pivot")
        lista = self.env.ref("lira_dashboard_contabilidad.view_lira_evolucion_coste_list")
        graph = self.env.ref("lira_dashboard_contabilidad.view_lira_evolucion_coste_graph")
        return {
            "type": "ir.actions.act_window",
            "name": "Evolución de costes vs facturación",
            "res_model": "lira.evolucion.coste.line",
            "view_mode": "pivot,graph,list",
            "views": [(pivot.id, "pivot"), (graph.id, "graph"), (lista.id, "list")],
            "domain": [("user_id", "=", self.env.user.id)],
            "context": {"create": False, "delete": False, "edit": False},
            "target": "current",
        }
