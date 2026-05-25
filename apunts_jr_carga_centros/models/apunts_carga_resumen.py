from odoo import api, fields, models


class ApuntsCargaResumen(models.TransientModel):
    _name = "apunts.carga.centros.resumen"
    _description = "Resumen carga centros — tarjetas globales"

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Resumen carga centros"

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
