from odoo import api, fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    apunts_horas_pendientes = fields.Float(
        string="Horas pendientes",
        compute="_compute_apunts_carga",
        help=(
            "Horas que QUEDAN POR HACER en este centro.\n"
            "\n"
            "FÓRMULA: SUMA de minutos previstos de los workorders en estado "
            "ready/pending/progress, dividido entre 60.\n"
            "\n"
            "No incluye workorders ya terminados (state='done')."
        ),
    )
    apunts_dias_pendientes = fields.Float(
        string="Días pendientes",
        compute="_compute_apunts_carga",
        help="Días laborales (8 h/día) equivalentes a las horas pendientes.",
    )
    apunts_horas_reales_semana = fields.Float(
        string="Horas reales (últimos 7 días)",
        compute="_compute_apunts_carga",
        help=(
            "Horas que los operarios HAN FICHADO en este centro durante los "
            "últimos 7 días (incluye hoy).\n"
            "\n"
            "FÓRMULA: SUMA de minutos de productividades cerradas en últimos 7 días, dividido entre 60."
        ),
    )
    apunts_dias_reales_semana = fields.Float(
        string="Días reales (7 días)",
        compute="_compute_apunts_carga",
        help="Días laborales (8 h/día) equivalentes a las horas reales fichadas en los últimos 7 días.",
    )
    apunts_n_workorders_pendientes = fields.Integer(
        string="Nº órdenes de trabajo abiertas",
        compute="_compute_apunts_carga",
        help="Cantidad de órdenes de trabajo en estado ready/pending/progress en este centro.",
    )
    apunts_horas_reales_15d = fields.Float(
        string="Horas reales (últimos 15 días)",
        compute="_compute_apunts_carga",
        help=(
            "Horas que los operarios HAN FICHADO en este centro durante los "
            "últimos 15 días (incluye hoy).\n"
            "\n"
            "FÓRMULA: SUMA de minutos de productividades cerradas en últimos 15 días, dividido entre 60."
        ),
    )
    apunts_dias_reales_15d = fields.Float(
        string="Días reales (15 días)",
        compute="_compute_apunts_carga",
        help="Días laborales (8 h/día) equivalentes a las horas reales fichadas en los últimos 15 días.",
    )
    apunts_horas_reales_30d = fields.Float(
        string="Horas reales (últimos 30 días)",
        compute="_compute_apunts_carga",
        help=(
            "Horas que los operarios HAN FICHADO en este centro durante los "
            "últimos 30 días (incluye hoy).\n"
            "\n"
            "FÓRMULA: SUMA de minutos de productividades cerradas en últimos 30 días, dividido entre 60."
        ),
    )
    apunts_dias_reales_30d = fields.Float(
        string="Días reales (30 días)",
        compute="_compute_apunts_carga",
        help="Días laborales (8 h/día) equivalentes a las horas reales fichadas en los últimos 30 días.",
    )
    apunts_horas_reales_total = fields.Float(
        string="Horas fichadas (total histórico)",
        compute="_compute_apunts_totales",
        help=(
            "Horas totales fichadas en este centro a lo largo de toda su historia.\n"
            "\n"
            "FÓRMULA: SUMA de minutos de TODAS las productividades cerradas "
            "(date_end IS NOT NULL), sin filtro temporal, dividido entre 60.\n"
            "\n"
            "Incluye todos los periodos desde que se empezó a fichar en este centro."
        ),
    )
    apunts_dias_reales_total = fields.Float(
        string="Días fichados (total histórico)",
        compute="_compute_apunts_totales",
        help=(
            "Días laborales (8 h/día) equivalentes al total histórico de horas fichadas "
            "en este centro. Ver 'Horas fichadas (total histórico)' para el detalle."
        ),
    )
    apunts_carga_pct = fields.Float(
        string="% carga (aprox. 30 días)",
        compute="_compute_apunts_carga_pct",
        help=(
            "Carga aproximada del centro para los próximos 30 días en porcentaje.\n"
            "\n"
            "FÓRMULA: (horas_pendientes / (horas_por_día_del_calendario × 30)) × 100.\n"
            "\n"
            "La capacidad diaria se obtiene del campo 'Horas medias/día' del calendario "
            "laboral asignado al centro (resource_calendar_id.hours_per_day). "
            "Si el centro no tiene calendario o las horas/día son 0, este campo muestra 0.\n"
            "\n"
            "Es una estimación: no tiene en cuenta festivos ni ausencias planificadas."
        ),
    )

    def _compute_apunts_carga(self):
        if not self:
            return
        cr = self.env.cr
        ids = tuple(self.ids) or (0,)
        # Horas pendientes y nº workorders abiertos
        cr.execute("""
            SELECT wo.workcenter_id,
                   COALESCE(SUM(wo.duration_expected), 0) / 60.0 AS horas_pte,
                   COUNT(*) AS n_wo
            FROM mrp_workorder wo
            WHERE wo.workcenter_id IN %s
              AND wo.state IN ('ready', 'pending', 'progress')
            GROUP BY wo.workcenter_id
        """, (ids,))
        pendientes = {row[0]: (row[1], row[2]) for row in cr.fetchall()}
        # Horas reales últimos 7 días
        cr.execute("""
            SELECT p.workcenter_id,
                   COALESCE(SUM(p.duration), 0) / 60.0 AS horas_real
            FROM mrp_workcenter_productivity p
            WHERE p.workcenter_id IN %s
              AND p.date_end IS NOT NULL
              AND p.date_end >= (NOW() - INTERVAL '7 days')
            GROUP BY p.workcenter_id
        """, (ids,))
        reales_7d = {row[0]: row[1] for row in cr.fetchall()}
        # Horas reales últimos 15 días
        cr.execute("""
            SELECT p.workcenter_id,
                   COALESCE(SUM(p.duration), 0) / 60.0 AS horas_real
            FROM mrp_workcenter_productivity p
            WHERE p.workcenter_id IN %s
              AND p.date_end IS NOT NULL
              AND p.date_end >= (NOW() - INTERVAL '15 days')
            GROUP BY p.workcenter_id
        """, (ids,))
        reales_15d = {row[0]: row[1] for row in cr.fetchall()}
        # Horas reales últimos 30 días
        cr.execute("""
            SELECT p.workcenter_id,
                   COALESCE(SUM(p.duration), 0) / 60.0 AS horas_real
            FROM mrp_workcenter_productivity p
            WHERE p.workcenter_id IN %s
              AND p.date_end IS NOT NULL
              AND p.date_end >= (NOW() - INTERVAL '30 days')
            GROUP BY p.workcenter_id
        """, (ids,))
        reales_30d = {row[0]: row[1] for row in cr.fetchall()}
        for w in self:
            horas_pte, n_wo = pendientes.get(w.id, (0.0, 0))
            horas_real_7d = float(reales_7d.get(w.id, 0.0) or 0.0)
            horas_real_15d = float(reales_15d.get(w.id, 0.0) or 0.0)
            horas_real_30d = float(reales_30d.get(w.id, 0.0) or 0.0)
            w.apunts_horas_pendientes = float(horas_pte or 0.0)
            w.apunts_dias_pendientes = float(horas_pte or 0.0) / 8.0
            w.apunts_n_workorders_pendientes = int(n_wo or 0)
            w.apunts_horas_reales_semana = horas_real_7d
            w.apunts_dias_reales_semana = horas_real_7d / 8.0
            w.apunts_horas_reales_15d = horas_real_15d
            w.apunts_dias_reales_15d = horas_real_15d / 8.0
            w.apunts_horas_reales_30d = horas_real_30d
            w.apunts_dias_reales_30d = horas_real_30d / 8.0

    def _compute_apunts_totales(self):
        if not self:
            return
        cr = self.env.cr
        ids = tuple(self.ids) or (0,)
        # Horas reales totales (sin filtro temporal)
        cr.execute("""
            SELECT p.workcenter_id,
                   COALESCE(SUM(p.duration), 0) / 60.0 AS horas_total
            FROM mrp_workcenter_productivity p
            WHERE p.workcenter_id IN %s
              AND p.date_end IS NOT NULL
            GROUP BY p.workcenter_id
        """, (ids,))
        totales = {row[0]: row[1] for row in cr.fetchall()}
        for w in self:
            horas_total = float(totales.get(w.id, 0.0) or 0.0)
            w.apunts_horas_reales_total = horas_total
            w.apunts_dias_reales_total = horas_total / 8.0

    def _compute_apunts_carga_pct(self):
        for w in self:
            horas_pte = w.apunts_horas_pendientes
            horas_dia = (
                w.resource_calendar_id.hours_per_day
                if w.resource_calendar_id and w.resource_calendar_id.hours_per_day
                else 0.0
            )
            if horas_dia > 0.0:
                w.apunts_carga_pct = (horas_pte / (horas_dia * 30.0)) * 100.0
            else:
                w.apunts_carga_pct = 0.0

    def action_apunts_open_workorders_pendientes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Órdenes de trabajo abiertas — {self.name}",
            "res_model": "mrp.workorder",
            "view_mode": "list,form",
            "domain": [
                ("workcenter_id", "=", self.id),
                ("state", "in", ("ready", "pending", "progress")),
            ],
        }
