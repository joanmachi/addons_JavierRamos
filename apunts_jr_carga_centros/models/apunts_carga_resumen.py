from datetime import datetime, time, timedelta

from odoo import api, fields, models


class ApuntsCargaResumen(models.TransientModel):
    _name = "apunts.carga.centros.resumen"
    _description = "Resumen carga centros — tarjetas globales"

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Resumen carga centros"

    modo = fields.Selection(
        [("en_curso", "En curso"), ("historico", "Histórico")],
        string="Vista",
        default="en_curso",
    )
    fecha_desde = fields.Date(string="Desde")
    fecha_hasta = fields.Date(string="Hasta")

    n_centros = fields.Integer(string="Nº centros", compute="_compute_resumen")
    n_centros_activos = fields.Integer(
        string="Centros con trabajo pendiente",
        compute="_compute_resumen",
    )
    total_horas_pendientes = fields.Float(
        string="Horas pendientes (total)",
        compute="_compute_resumen",
    )
    total_dias_pendientes = fields.Float(
        string="Días de trabajo pendientes (total)",
        compute="_compute_resumen",
    )
    total_horas_reales_semana = fields.Float(
        string="Horas reales últimos 7 días (total)",
        compute="_compute_resumen",
    )
    total_horas_reales_total = fields.Float(
        string="Horas fichadas (total histórico)",
        compute="_compute_resumen",
    )
    total_dias_reales_total = fields.Float(
        string="Días fichados (total histórico)",
        compute="_compute_resumen",
    )
    total_horas_reales_15d = fields.Float(
        string="Horas reales últimos 15 días (total)",
        compute="_compute_resumen",
    )
    total_dias_reales_15d = fields.Float(
        string="Días reales últimos 15 días (total)",
        compute="_compute_resumen",
    )
    total_horas_reales_30d = fields.Float(
        string="Horas reales últimos 30 días (total)",
        compute="_compute_resumen",
    )
    total_dias_reales_30d = fields.Float(
        string="Días reales últimos 30 días (total)",
        compute="_compute_resumen",
    )
    total_workorders_pendientes = fields.Integer(
        string="Órdenes de trabajo abiertas (total)",
        compute="_compute_resumen",
    )

    @api.depends_context("uid")
    def _compute_resumen(self):
        WC = self.env["mrp.workcenter"]
        centros = WC.search([("active", "=", True)])
        for rec in self:
            rec.n_centros = len(centros)
            rec.n_centros_activos = sum(
                1 for c in centros if c.apunts_horas_pendientes > 0
            )
            horas_pte = sum(centros.mapped("apunts_horas_pendientes"))
            rec.total_horas_pendientes = horas_pte
            rec.total_dias_pendientes = horas_pte / 8.0
            rec.total_horas_reales_semana = sum(
                centros.mapped("apunts_horas_reales_semana")
            )
            rec.total_horas_reales_15d = sum(
                centros.mapped("apunts_horas_reales_15d")
            )
            rec.total_dias_reales_15d = sum(
                centros.mapped("apunts_dias_reales_15d")
            )
            rec.total_horas_reales_30d = sum(
                centros.mapped("apunts_horas_reales_30d")
            )
            rec.total_dias_reales_30d = sum(
                centros.mapped("apunts_dias_reales_30d")
            )
            rec.total_horas_reales_total = sum(
                centros.mapped("apunts_horas_reales_total")
            )
            rec.total_dias_reales_total = sum(
                centros.mapped("apunts_dias_reales_total")
            )
            rec.total_workorders_pendientes = sum(
                centros.mapped("apunts_n_workorders_pendientes")
            )

    # ── Histórico: horas fichadas en un rango de fechas ──────────────────────

    hist_n_centros = fields.Integer(
        string="Centros que trabajaron",
        compute="_compute_historico",
        help="Nº de centros de trabajo con al menos un fichaje cerrado en el periodo.",
    )
    hist_n_fichajes = fields.Integer(
        string="Fichajes cerrados",
        compute="_compute_historico",
        help="Nº de fichajes de operario cerrados en el periodo.",
    )
    hist_horas = fields.Float(
        string="Horas fichadas (periodo)",
        compute="_compute_historico",
        help=(
            "Horas fichadas por operarios en todos los centros dentro del "
            "periodo seleccionado (por fecha de cierre del fichaje). Sin "
            "fechas: todo el histórico."
        ),
    )
    hist_dias = fields.Float(
        string="Días equivalentes (periodo)",
        compute="_compute_historico",
        help="Días laborales (8 h/día) equivalentes a las horas fichadas del periodo.",
    )
    hist_horas_media_dia = fields.Float(
        string="Horas/día de media",
        compute="_compute_historico",
        help=(
            "Horas fichadas del periodo divididas entre los días naturales "
            "del rango. Solo se calcula si has puesto Desde y Hasta."
        ),
    )

    def _hist_rango_utc(self, rec):
        """(desde, hasta_exclusivo) como datetimes naive para filtrar
        date_end, o None si no hay fecha."""
        desde = hasta = None
        if rec.fecha_desde:
            desde = datetime.combine(rec.fecha_desde, time.min)
        if rec.fecha_hasta:
            hasta = datetime.combine(
                rec.fecha_hasta + timedelta(days=1), time.min
            )
        return desde, hasta

    @api.depends("modo", "fecha_desde", "fecha_hasta")
    @api.depends_context("uid")
    def _compute_historico(self):
        cr = self.env.cr
        for rec in self:
            desde, hasta = self._hist_rango_utc(rec)
            where = [
                "p.date_end IS NOT NULL",
                "p.workcenter_id IS NOT NULL",
            ]
            params = []
            if desde:
                where.append("p.date_end >= %s")
                params.append(desde)
            if hasta:
                where.append("p.date_end < %s")
                params.append(hasta)
            cr.execute(
                """
                SELECT COUNT(DISTINCT p.workcenter_id),
                       COUNT(*),
                       COALESCE(SUM(p.duration), 0) / 60.0
                FROM mrp_workcenter_productivity p
                WHERE %s
                """
                % " AND ".join(where),
                params,
            )
            n_centros, n_fichajes, horas = cr.fetchone() or (0, 0, 0.0)
            rec.hist_n_centros = int(n_centros or 0)
            rec.hist_n_fichajes = int(n_fichajes or 0)
            rec.hist_horas = float(horas or 0.0)
            rec.hist_dias = rec.hist_horas / 8.0
            if rec.fecha_desde and rec.fecha_hasta and rec.fecha_hasta >= rec.fecha_desde:
                dias_rango = (rec.fecha_hasta - rec.fecha_desde).days + 1
                rec.hist_horas_media_dia = rec.hist_horas / dias_rango
            else:
                rec.hist_horas_media_dia = 0.0

    def action_open_historico_centros(self):
        """Desglose del periodo: fichajes agrupados por centro (lista + pivote)."""
        self.ensure_one()
        desde, hasta = self._hist_rango_utc(self)
        domain = [("date_end", "!=", False), ("workcenter_id", "!=", False)]
        if desde:
            domain.append(("date_end", ">=", fields.Datetime.to_string(desde)))
        if hasta:
            domain.append(("date_end", "<", fields.Datetime.to_string(hasta)))
        return {
            "type": "ir.actions.act_window",
            "name": "Histórico por centro",
            "res_model": "mrp.workcenter.productivity",
            "view_mode": "pivot,list",
            "views": [
                (self.env.ref("apunts_jr_carga_centros.apunts_carga_hist_pivot").id, "pivot"),
                (self.env.ref("apunts_jr_carga_centros.apunts_carga_hist_list").id, "list"),
            ],
            "domain": domain,
            "context": {"group_by": ["workcenter_id"]},
        }

    def action_open_lista_centros(self):
        return self.env.ref(
            "apunts_jr_carga_centros.apunts_action_carga_centros_list"
        ).read()[0]

    @api.model
    def action_open_resumen(self):
        rec = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Resumen carga centros",
            "res_model": "apunts.carga.centros.resumen",
            "view_mode": "form",
            "view_id": self.env.ref(
                "apunts_jr_carga_centros.apunts_carga_resumen_form"
            ).id,
            "res_id": rec.id,
            "target": "current",
        }
