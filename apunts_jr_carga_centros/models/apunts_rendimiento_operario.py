"""Rendimiento por operario: cuántas horas de trabajo PREVISTO se completan por
cada hora fichada. Es el indicador de "productividad = 1" del cuadro de mando
antiguo del cliente: 1,00 = se cumple el tiempo previsto; más de 1 = se va más
rápido; menos de 1 = se tarda más.

Método (importante para que el número sea honesto):
- Solo cuentan las órdenes de trabajo TERMINADAS. En una OT a medias todavía no
  se ha "ganado" el tiempo previsto, y contarla dispara el ratio.
- Las horas previstas de cada OT se reparten entre quienes ficharon en ella, en
  proporción al tiempo que fichó cada uno.
- Se excluyen los empleados marcados como "No contar en rendimiento" (cuentas que
  no son operarios: la empresa, Planta, Gestión, usuarios de prueba...).
"""

from datetime import date, datetime, time, timedelta

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    apunts_excluir_rendimiento = fields.Boolean(
        string="No contar en rendimiento",
        help="Marca las fichas que NO son un operario real (la empresa, centros "
             "genéricos como 'Planta' o 'Gestión', usuarios de prueba...). Sus "
             "fichajes no entran en el rendimiento por operario, que si no queda "
             "distorsionado.",
    )


class ApuntsRendimientoOperarioLine(models.Model):
    _name = "apunts.rendimiento.operario.line"
    _description = "Rendimiento por operario (línea)"
    _order = "rendimiento desc"

    user_id = fields.Many2one("res.users", ondelete="cascade", index=True)
    employee_id = fields.Many2one("hr.employee", string="Operario")
    horas_fichadas = fields.Float(string="Horas fichadas", digits=(16, 1))
    horas_ganadas = fields.Float(string="Horas de trabajo hechas", digits=(16, 1))
    rendimiento = fields.Float(string="Rendimiento", digits=(16, 2))
    n_ot = fields.Integer(string="OT terminadas")
    llega = fields.Boolean(string="Llega a 1")

    def action_open_fichajes(self):
        """Los fichajes del operario en el periodo analizado."""
        self.ensure_one()
        ctx = self.env.context
        dom = [("employee_id", "=", self.employee_id.id), ("date_end", "!=", False)]
        if ctx.get("apunts_desde"):
            dom.append(("date_end", ">=", ctx["apunts_desde"]))
        if ctx.get("apunts_hasta"):
            dom.append(("date_end", "<", ctx["apunts_hasta"]))
        return {
            "type": "ir.actions.act_window",
            "name": "Fichajes de %s" % (self.employee_id.name or ""),
            "res_model": "mrp.workcenter.productivity",
            "view_mode": "list,form",
            "domain": dom,
        }


class ApuntsRendimientoOperario(models.TransientModel):
    _name = "apunts.rendimiento.operario"
    _description = "Rendimiento por operario"

    fecha_desde = fields.Date(string="Desde")
    fecha_hasta = fields.Date(string="Hasta")

    def _rango(self):
        self.ensure_one()
        desde = datetime.combine(self.fecha_desde, time.min) if self.fecha_desde else None
        hasta = (datetime.combine(self.fecha_hasta + timedelta(days=1), time.min)
                 if self.fecha_hasta else None)
        return desde, hasta

    def _calcular(self):
        """Devuelve [(employee_id, horas_fichadas, horas_ganadas, n_ot)]."""
        self.ensure_one()
        desde, hasta = self._rango()
        where = [
            "p.date_end IS NOT NULL",
            "p.employee_id IS NOT NULL",
            "wo.state = 'done'",            # solo OT terminadas: lo ya ganado de verdad
            "COALESCE(e.apunts_excluir_rendimiento, FALSE) = FALSE",
        ]
        params = []
        if desde:
            where.append("p.date_end >= %s")
            params.append(desde)
        if hasta:
            where.append("p.date_end < %s")
            params.append(hasta)
        self.env.cr.execute(
            """
            WITH wo_real AS (
                SELECT workorder_id, SUM(duration) AS tot_real
                FROM mrp_workcenter_productivity
                WHERE workorder_id IS NOT NULL AND date_end IS NOT NULL
                GROUP BY workorder_id
            )
            SELECT p.employee_id,
                   SUM(p.duration) / 60.0 AS fichadas,
                   SUM(wo.duration_expected * (p.duration::float / NULLIF(wr.tot_real, 0)))
                       / 60.0 AS ganadas,
                   COUNT(DISTINCT wo.id) AS n_ot
            FROM mrp_workcenter_productivity p
            JOIN mrp_workorder wo ON wo.id = p.workorder_id
            JOIN wo_real wr ON wr.workorder_id = p.workorder_id
            JOIN hr_employee e ON e.id = p.employee_id
            WHERE %s
            GROUP BY p.employee_id
            HAVING SUM(p.duration) > 0
            """
            % " AND ".join(where),
            params,
        )
        return self.env.cr.fetchall()

    def _store_lines(self):
        self.ensure_one()
        Line = self.env["apunts.rendimiento.operario.line"]
        Line.search([("user_id", "=", self.env.user.id)]).unlink()
        for emp_id, fichadas, ganadas, n_ot in self._calcular():
            fichadas = float(fichadas or 0.0)
            ganadas = float(ganadas or 0.0)
            rend = (ganadas / fichadas) if fichadas else 0.0
            Line.create({
                "user_id": self.env.user.id,
                "employee_id": emp_id,
                "horas_fichadas": fichadas,
                "horas_ganadas": ganadas,
                "rendimiento": rend,
                "n_ot": int(n_ot or 0),
                "llega": rend >= 1.0,
            })

    def action_ver(self):
        self.ensure_one()
        self._store_lines()
        desde, hasta = self._rango()
        graph = self.env.ref("apunts_jr_carga_centros.apunts_rendimiento_operario_graph")
        lista = self.env.ref("apunts_jr_carga_centros.apunts_rendimiento_operario_list")
        ctx = {"create": False, "delete": False, "edit": False}
        if desde:
            ctx["apunts_desde"] = fields.Datetime.to_string(desde)
        if hasta:
            ctx["apunts_hasta"] = fields.Datetime.to_string(hasta)
        return {
            "type": "ir.actions.act_window",
            "name": "Rendimiento por operario",
            "res_model": "apunts.rendimiento.operario.line",
            "view_mode": "list,graph",
            "views": [(lista.id, "list"), (graph.id, "graph")],
            "domain": [("user_id", "=", self.env.user.id)],
            "context": ctx,
            "target": "current",
        }

    @api.model
    def action_open(self):
        """Entrada por defecto: últimos 90 días."""
        hoy = date.today()
        rec = self.create({
            "fecha_desde": hoy - timedelta(days=90),
            "fecha_hasta": hoy,
        })
        return rec.action_ver()
