"""Consultar la reunión semanal de otra semana.

La reunión del lunes trabaja siempre con la última semana. Aquí se elige un
rango de fechas y se abre el mismo panel (indicadores → KPIs) tal y como
quedó guardado esa semana: la cobertura de cartera que había, el EDV, la
eficiencia... Si el rango abarca varias semanas se abre la tabla de KPIs por
semanas para compararlas.
"""

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class ApuntsKpiConsulta(models.TransientModel):
    _name = "apunts.kpi.consulta"
    _description = "Reunión semanal · consultar otra semana"

    fecha_desde = fields.Date(string="Desde", required=True,
                              default=lambda s: s._lunes_ultima_cerrada())
    fecha_hasta = fields.Date(string="Hasta", required=True,
                              default=lambda s: s._fin_por_defecto())
    semanas_txt = fields.Char(compute="_compute_semanas_txt", string="Semanas en el rango")

    @api.model
    def _fin_por_defecto(self):
        rango = self.env.context.get("apunts_rango")
        if rango:
            return fields.Date.to_date(rango[1]) + timedelta(days=6)
        return self._lunes_ultima_cerrada() + timedelta(days=6)

    @api.model
    def _lunes_ultima_cerrada(self):
        # Abierto desde un periodo o una semana concreta: propone lo mismo
        rango = self.env.context.get("apunts_rango")
        if rango:
            return fields.Date.to_date(rango[0])
        ctx = self.env.context.get("apunts_semana")
        if ctx:
            d = fields.Date.to_date(ctx)
            return d - timedelta(days=d.weekday())
        ultima = self.env["apunts.kpi.semana"].sudo().search(
            [("cerrada", "=", True)], order="fecha desc", limit=1)
        if ultima:
            return ultima.fecha
        hoy = fields.Date.context_today(self)
        return hoy - timedelta(days=hoy.weekday() + 7)

    def _lunes_del_rango(self):
        """Lunes (con dato) de cada semana ISO que toca el rango."""
        self.ensure_one()
        if self.fecha_hasta < self.fecha_desde:
            raise UserError("La fecha «Hasta» no puede ser anterior a «Desde».")
        lunes_ini = self.fecha_desde - timedelta(days=self.fecha_desde.weekday())
        lunes_fin = self.fecha_hasta - timedelta(days=self.fecha_hasta.weekday())
        filas = self.env["apunts.kpi.semana"].sudo().read_group(
            [("fecha", ">=", lunes_ini), ("fecha", "<=", lunes_fin)],
            ["fecha"], ["fecha:day"], orderby="fecha")
        return sorted({fields.Date.to_date(f["__range"]["fecha:day"]["from"]) for f in filas})

    @api.depends("fecha_desde", "fecha_hasta")
    def _compute_semanas_txt(self):
        for w in self:
            try:
                lunes = w._lunes_del_rango() if w.fecha_desde and w.fecha_hasta else []
            except UserError:
                lunes = []
            if not lunes:
                w.semanas_txt = "No hay ninguna semana guardada en ese rango."
            elif len(lunes) == 1:
                iso = lunes[0].isocalendar()
                w.semanas_txt = "Una semana: S%02d/%s (del %s al %s). Se abrirá el panel de esa semana." % (
                    iso[1], iso[0], lunes[0].strftime("%d/%m"), (lunes[0] + timedelta(days=6)).strftime("%d/%m"))
            else:
                w.semanas_txt = "%d semanas, de la S%02d/%s a la S%02d/%s. Se abrirá el resumen del periodo (acumulado), con opción de verlo semana a semana." % (
                    len(lunes), lunes[0].isocalendar()[1], lunes[0].isocalendar()[0],
                    lunes[-1].isocalendar()[1], lunes[-1].isocalendar()[0])

    def action_consultar(self):
        self.ensure_one()
        lunes = self._lunes_del_rango()
        if not lunes:
            raise UserError("No hay ninguna semana guardada entre esas fechas. "
                            "El registro empieza en la primera semana que se cerró.")
        if len(lunes) == 1:
            return self.env["apunts.kpi.bloque"].action_reunion_semana(lunes[0])
        # Varias semanas: el resumen del periodo (acumulado) en las tarjetas de
        # siempre; desde ahí, «Ver por semanas» abre una columna por semana.
        return self.env["apunts.kpi.bloque"].action_reunion_rango(lunes[0], lunes[-1])

    @api.model
    def _accion_por_semanas(self, lunes_ini, lunes_fin):
        """Las tarjetas en una columna por semana. De entrada solo el KPI
        principal de cada indicador (6 por semana); sin el filtro, los 33."""
        kanban = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_semana_kanban")
        pivot = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_semana_pivot")
        lista = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_semana_list")
        search = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_semana_search")
        return {
            "type": "ir.actions.act_window",
            "name": "Semana a semana · S%02d/%s a S%02d/%s" % (
                lunes_ini.isocalendar()[1], lunes_ini.isocalendar()[0],
                lunes_fin.isocalendar()[1], lunes_fin.isocalendar()[0]),
            "res_model": "apunts.kpi.semana",
            "view_mode": "kanban,pivot,list",
            "views": [(kanban.id, "kanban"), (pivot.id, "pivot"), (lista.id, "list")],
            "search_view_id": [search.id, "search"],
            "domain": [("fecha", ">=", lunes_ini), ("fecha", "<=", lunes_fin)],
            "context": {"search_default_g_semana": 1, "search_default_f_principales": 1,
                        "create": False, "delete": False},
            "target": "current",
        }


class ApuntsKpiBloqueNavegacion(models.Model):
    """Botones de la cabecera de la Reunión semanal: semana anterior /
    siguiente y elegir fechas, sin salir del panel."""

    _inherit = "apunts.kpi.bloque"

    @api.model
    def _lunes_ultimo(self):
        ultima = self.env["apunts.kpi.semana"].sudo().search([], order="fecha desc", limit=1)
        d = ultima.fecha or fields.Date.context_today(self)
        return d - timedelta(days=d.weekday())

    @api.model
    def action_reunion_rango(self, lunes_ini, lunes_fin):
        """El panel con el ACUMULADO del periodo: flujos sumados, ratios
        semanales en media, acumulados del año y fotos a cierre."""
        kanban = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_bloque_kanban")
        iso_i, iso_f = lunes_ini.isocalendar(), lunes_fin.isocalendar()
        return {
            "type": "ir.actions.act_window",
            "name": "Reunión semanal · periodo S%02d/%s a S%02d/%s (del %s al %s)" % (
                iso_i[1], iso_i[0], iso_f[1], iso_f[0],
                lunes_ini.strftime("%d/%m"), (lunes_fin + timedelta(days=6)).strftime("%d/%m")),
            "res_model": "apunts.kpi.bloque",
            "view_mode": "kanban,list",
            "views": [(kanban.id, "kanban"), (False, "list")],
            "context": {"apunts_rango": [fields.Date.to_string(lunes_ini), fields.Date.to_string(lunes_fin)],
                        "create": False, "delete": False},
            "target": "current",
        }

    @api.model
    def action_ver_por_semanas(self):
        """Botón de cabecera: el periodo (o la semana) que se está viendo, en
        una columna por semana. Sin nada elegido, las últimas 6 semanas."""
        rango = self.env.context.get("apunts_rango")
        if rango:
            ini, fin = fields.Date.to_date(rango[0]), fields.Date.to_date(rango[1])
        else:
            fin = self._lunes_contexto()
            ini = fin - timedelta(days=7 * 5)
        return self.env["apunts.kpi.consulta"]._accion_por_semanas(ini, fin)

    @api.model
    def _lunes_contexto(self):
        """La semana que se está viendo: la del contexto (o el final del
        periodo consultado) o, si no hay, la última."""
        rango = self.env.context.get("apunts_rango")
        if rango:
            d = fields.Date.to_date(rango[1])
            return d - timedelta(days=d.weekday())
        ctx = self.env.context.get("apunts_semana")
        if ctx:
            d = fields.Date.to_date(ctx)
            return d - timedelta(days=d.weekday())
        return self._lunes_ultimo()

    @api.model
    def action_reunion_semana(self, lunes):
        """El panel de la reunión de la semana que empieza ese lunes. Si es la
        última semana registrada, el panel normal (sin semana fijada)."""
        if lunes >= self._lunes_ultimo():
            accion = self.env.ref("apunts_jr_dashboard_direccion.apunts_action_kpi_bloques").sudo().read()[0]
            accion["context"] = {"create": False, "delete": False}
            return accion
        iso = lunes.isocalendar()
        kanban = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_bloque_kanban")
        return {
            "type": "ir.actions.act_window",
            "name": "Reunión semanal · S%02d/%s (del %s al %s)" % (
                iso[1], iso[0], lunes.strftime("%d/%m"), (lunes + timedelta(days=6)).strftime("%d/%m")),
            "res_model": "apunts.kpi.bloque",
            "view_mode": "kanban,list",
            "views": [(kanban.id, "kanban"), (False, "list")],
            "context": {"apunts_semana": fields.Date.to_string(lunes), "create": False, "delete": False},
            "target": "current",
        }

    @api.model
    def action_semana_anterior(self):
        return self.action_reunion_semana(self._lunes_contexto() - timedelta(days=7))

    @api.model
    def action_semana_siguiente(self):
        return self.action_reunion_semana(self._lunes_contexto() + timedelta(days=7))
