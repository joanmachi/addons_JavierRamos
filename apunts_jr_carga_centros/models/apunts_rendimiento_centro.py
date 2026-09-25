# -*- coding: utf-8 -*-
"""Rendimiento por centro de trabajo: tiempo previsto frente a tiempo real,
igual que el rendimiento por operario pero por máquina/centro. 1,00 = el centro
cumple el tiempo previsto de las órdenes que termina."""
from datetime import date, timedelta

from odoo import api, fields, models


class ApuntsRendimientoCentroLine(models.Model):
    _name = "apunts.rendimiento.centro.line"
    _description = "Rendimiento por centro (línea)"
    _order = "rendimiento desc"

    user_id = fields.Many2one("res.users", ondelete="cascade", index=True)
    workcenter_id = fields.Many2one("mrp.workcenter", string="Centro")
    horas_fichadas = fields.Float(string="Horas fichadas", digits=(16, 1))
    horas_previstas = fields.Float(string="Horas previstas", digits=(16, 1))
    rendimiento = fields.Float(string="Rendimiento", digits=(16, 2),
                               help="Horas previstas ÷ horas fichadas de las órdenes "
                                    "terminadas. 1,00 = se cumple el tiempo previsto.")
    n_ot = fields.Integer(string="OT terminadas")
    llega = fields.Boolean(string="Llega a 1")

    def action_open_fichajes(self):
        self.ensure_one()
        ctx = self.env.context
        dom = [("workcenter_id", "=", self.workcenter_id.id), ("date_end", "!=", False)]
        if ctx.get("apunts_desde"):
            dom.append(("date_end", ">=", ctx["apunts_desde"]))
        if ctx.get("apunts_hasta"):
            dom.append(("date_end", "<", ctx["apunts_hasta"]))
        return {
            "type": "ir.actions.act_window",
            "name": "Fichajes de %s" % (self.workcenter_id.name or ""),
            "res_model": "mrp.workcenter.productivity",
            "view_mode": "list,form",
            "domain": dom,
        }


class ApuntsRendimientoCentro(models.TransientModel):
    _name = "apunts.rendimiento.centro"
    _description = "Rendimiento por centro"

    fecha_desde = fields.Date(string="Desde")
    fecha_hasta = fields.Date(string="Hasta")

    def _rango(self):
        self.ensure_one()
        from datetime import datetime, time
        desde = datetime.combine(self.fecha_desde, time.min) if self.fecha_desde else None
        hasta = (datetime.combine(self.fecha_hasta + timedelta(days=1), time.min)
                 if self.fecha_hasta else None)
        return desde, hasta

    def _store_lines(self):
        self.ensure_one()
        desde, hasta = self._rango()
        Line = self.env["apunts.rendimiento.centro.line"]
        Line.search([("user_id", "=", self.env.user.id)]).unlink()
        # Horas fichadas por centro en el rango
        cond, params = ["p.date_end IS NOT NULL", "p.workcenter_id IS NOT NULL"], []
        if desde:
            cond.append("p.date_end >= %s"); params.append(desde)
        if hasta:
            cond.append("p.date_end < %s"); params.append(hasta)
        self.env.cr.execute("""
            SELECT p.workcenter_id, SUM(p.duration)/60.0
            FROM mrp_workcenter_productivity p
            WHERE %s GROUP BY p.workcenter_id""" % " AND ".join(cond), params)
        fichadas = {r[0]: float(r[1] or 0) for r in self.env.cr.fetchall()}
        # Horas previstas de las OT TERMINADAS del centro en el rango
        cond2, params2 = ["wo.state = 'done'", "wo.workcenter_id IS NOT NULL"], []
        if desde:
            cond2.append("wo.date_finished >= %s"); params2.append(desde)
        if hasta:
            cond2.append("wo.date_finished < %s"); params2.append(hasta)
        self.env.cr.execute("""
            SELECT wo.workcenter_id, SUM(wo.duration_expected)/60.0, COUNT(*)
            FROM mrp_workorder wo
            WHERE %s GROUP BY wo.workcenter_id""" % " AND ".join(cond2), params2)
        previstas = {r[0]: (float(r[1] or 0), int(r[2] or 0)) for r in self.env.cr.fetchall()}
        for wc_id, horas in fichadas.items():
            # Menos de media hora fichada en todo el periodo: es un resto, no
            # actividad. Sin esto salian rendimientos absurdos (66x) al dividir
            # entre casi cero.
            if horas < 0.5:
                continue
            prev, n_ot = previstas.get(wc_id, (0.0, 0))
            rend = (prev / horas) if horas else 0.0
            Line.create({"user_id": self.env.user.id, "workcenter_id": wc_id,
                         "horas_fichadas": horas, "horas_previstas": prev,
                         "rendimiento": rend, "n_ot": n_ot, "llega": rend >= 1.0})

    def action_ver(self):
        self.ensure_one()
        self._store_lines()
        desde, hasta = self._rango()
        lista = self.env.ref("apunts_jr_carga_centros.apunts_rendimiento_centro_list")
        graph = self.env.ref("apunts_jr_carga_centros.apunts_rendimiento_centro_graph")
        ctx = {"create": False, "delete": False, "edit": False}
        if desde:
            ctx["apunts_desde"] = fields.Datetime.to_string(desde)
        if hasta:
            ctx["apunts_hasta"] = fields.Datetime.to_string(hasta)
        return {
            "type": "ir.actions.act_window",
            "name": "Rendimiento por centro",
            "res_model": "apunts.rendimiento.centro.line",
            "view_mode": "list,graph",
            "views": [(lista.id, "list"), (graph.id, "graph")],
            "domain": [("user_id", "=", self.env.user.id)],
            "context": ctx,
            "target": "current",
        }

    @api.model
    def action_open(self):
        hoy = date.today()
        rec = self.create({"fecha_desde": hoy - timedelta(days=90), "fecha_hasta": hoy})
        return rec.action_ver()
