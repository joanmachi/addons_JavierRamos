"""DAT · Días de autonomía de tesorería.

Cuántos días aguanta la caja si solo entran los cobros previstos y salen los
pagos previstos. Los vencimientos de clientes y proveedores están en Odoo; lo
que NO está como vencimiento (nóminas, Seguridad Social, IVA, préstamos...) se
configura aquí como pagos recurrentes, con una estimación inicial que la
empresa puede corregir.
"""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

CURVA_DIAS = 183  # medio año de proyección en la gráfica


class ApuntsDatPago(models.Model):
    _name = "apunts.dat.pago"
    _description = "DAT — pago recurrente previsto"
    _order = "dia, name"

    name = fields.Char(string="Concepto", required=True)
    importe = fields.Float(string="Importe (€)", digits=(16, 2), required=True)
    periodicidad = fields.Selection(
        [("mensual", "Cada mes"), ("trimestral", "Cada trimestre"), ("anual", "Una vez al año")],
        string="Periodicidad", required=True, default="mensual")
    dia = fields.Integer(string="Día del mes", default=28,
                         help="Día en que sale el dinero (1–28).")
    mes_ref = fields.Integer(string="Primer mes", default=1,
                             help="Para trimestrales/anuales: mes del primer pago (1 = enero). "
                                  "Un trimestral con primer mes 1 paga en enero, abril, julio y octubre.")
    activo = fields.Boolean(string="Activo", default=True)
    notas = fields.Char(string="Notas")

    @api.model
    def fechas(self, desde, hasta):
        """{fecha: importe} de todos los pagos recurrentes entre dos fechas."""
        res = {}
        for p in self.search([("activo", "=", True)]):
            dia = min(max(p.dia or 28, 1), 28)
            if p.periodicidad == "mensual":
                meses = range(1, 13)
            elif p.periodicidad == "trimestral":
                m0 = ((p.mes_ref or 1) - 1) % 3
                meses = [m for m in range(1, 13) if (m - 1) % 3 == m0]
            else:
                meses = [((p.mes_ref or 1) - 1) % 12 + 1]
            for anio in range(desde.year, hasta.year + 1):
                for m in meses:
                    f = date(anio, m, dia)
                    if desde <= f <= hasta:
                        res[f] = res.get(f, 0.0) + p.importe
        return res

    @api.model
    def _sembrar(self):
        """Estimaciones iniciales a partir de la contabilidad del año, para que
        el DAT no salga vacío. La empresa las ajusta en la pantalla."""
        if self.search_count([]):
            return 0
        hoy = fields.Date.context_today(self)
        cid = self.env.company.id
        meses = max(hoy.month - 1, 1)
        self.env.cr.execute("""
            SELECT COALESCE(SUM(aml.balance), 0) FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aml.date >= %s AND aa.code_store->>%s LIKE '64%%'""",
            (cid, date(hoy.year, 1, 1), str(cid)))
        personal = float(self.env.cr.fetchone()[0] or 0.0) / meses
        self.env.cr.execute("""
            SELECT COALESCE(SUM(aml.balance), 0) FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.parent_state = 'posted' AND aml.company_id = %s
              AND aa.code_store->>%s LIKE '477%%'""", (cid, str(cid)))
        iva = abs(float(self.env.cr.fetchone()[0] or 0.0))
        self.create([
            {"name": "Nóminas y Seguridad Social", "importe": round(personal, 2),
             "periodicidad": "mensual", "dia": 28,
             "notas": "Estimado con la media mensual de 2026 (cuentas 64x). Ajustar."},
            {"name": "IVA trimestral", "importe": round(iva, 2), "periodicidad": "trimestral",
             "dia": 20, "mes_ref": 1,
             "notas": "Estimado con el saldo actual de IVA repercutido (477). Ajustar."},
        ])
        return 2

    @api.model
    def action_proyeccion(self):
        """La curva: tesorería real de las últimas semanas + proyección día a
        día hacia delante, con el DAT resultante."""
        Motor = self.env["apunts.kpi.motor"]
        hoy = fields.Date.context_today(self)
        dias, lineas = Motor._dat(hoy, con_proyeccion=True)
        Line = self.env["apunts.dat.proyeccion.line"]
        Line.search([("user_id", "=", self.env.user.id)]).unlink()
        vals = []
        # Tesorería real: el histórico semanal que ya guarda el panel
        hist = self.env["apunts.kpi.semana"].sudo().search(
            [("clave", "=", "tesoreria_eur"), ("fecha", ">=", hoy - timedelta(days=91))],
            order="fecha")
        for h in hist:
            vals.append({"user_id": self.env.user.id, "fecha": h.fecha, "tipo": "real",
                         "saldo": h.valor})
        # La curva enseña el primer medio año día a día (el DAT se calcula a un año)
        for l in lineas[:CURVA_DIAS]:
            vals.append({"user_id": self.env.user.id, "fecha": l["fecha"], "tipo": "previsto",
                         "saldo": l["saldo"], "cobros": l["cobros"], "pagos": l["pagos"],
                         "recurrentes": l["recurrentes"]})
        Line.create(vals)
        graph = self.env.ref("apunts_jr_dashboard_direccion.apunts_dat_proyeccion_graph")
        lista = self.env.ref("apunts_jr_dashboard_direccion.apunts_dat_proyeccion_list")
        return {
            "type": "ir.actions.act_window",
            "name": "DAT · autonomía de tesorería: %s días" % dias,
            "res_model": "apunts.dat.proyeccion.line",
            "view_mode": "graph,list",
            "views": [(graph.id, "graph"), (lista.id, "list")],
            "domain": [("user_id", "=", self.env.user.id)],
            "context": {"fill_temporal": False, "create": False, "delete": False, "edit": False},
            "target": "current",
        }


class ApuntsDatProyeccionLine(models.TransientModel):
    _name = "apunts.dat.proyeccion.line"
    _description = "DAT — punto de la curva de tesorería"
    _order = "fecha"

    user_id = fields.Many2one("res.users", index=True)
    fecha = fields.Date(string="Fecha")
    tipo = fields.Selection([("real", "Tesorería real"), ("previsto", "Proyección")], string="Serie")
    saldo = fields.Float(string="Saldo (€)", digits=(16, 2))
    cobros = fields.Float(string="Cobros previstos", digits=(16, 2))
    pagos = fields.Float(string="Pagos previstos", digits=(16, 2))
    recurrentes = fields.Float(string="Pagos recurrentes", digits=(16, 2))
