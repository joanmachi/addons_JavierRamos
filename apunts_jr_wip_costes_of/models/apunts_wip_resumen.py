from datetime import timedelta

from odoo import api, fields, models


class ApuntsWipResumen(models.TransientModel):
    _name = "apunts.wip.resumen"
    _description = "Resumen WIP — tarjetas de totales globales"

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Resumen WIP"

    modo = fields.Selection(
        [("en_curso", "En curso"), ("historico", "Historial")],
        string="Vista",
        default="en_curso",
    )
    fecha_desde = fields.Date(string="Desde")
    fecha_hasta = fields.Date(string="Hasta")

    n_ofs_wip = fields.Integer(string="OFs", compute="_compute_resumen")
    total_venta = fields.Monetary(string="Venta total", compute="_compute_resumen", currency_field="currency_id")
    total_mat_planned = fields.Monetary(string="MP teórica", compute="_compute_resumen", currency_field="currency_id")
    total_mat_real = fields.Monetary(string="MP real", compute="_compute_resumen", currency_field="currency_id")
    total_mo_planned = fields.Monetary(string="Coste operario teórico", compute="_compute_resumen", currency_field="currency_id")
    total_mo_real = fields.Monetary(string="Coste operario real", compute="_compute_resumen", currency_field="currency_id")
    total_machine_planned = fields.Monetary(string="Coste máquina teórico", compute="_compute_resumen", currency_field="currency_id")
    total_machine_real = fields.Monetary(string="Coste máquina real", compute="_compute_resumen", currency_field="currency_id")
    total_min_planned = fields.Float(string="Minutos teóricos (OF)", compute="_compute_resumen")
    total_min_real = fields.Float(string="Minutos reales fichados", compute="_compute_resumen")
    total_horas_planned = fields.Float(string="Horas teóricas", compute="_compute_resumen")
    total_horas_real = fields.Float(string="Horas reales", compute="_compute_resumen")
    total_jornadas_planned = fields.Float(string="Días laborales teóricos (8h)", compute="_compute_resumen")
    total_jornadas_real = fields.Float(string="Días laborales reales (8h)", compute="_compute_resumen")
    total_mp_pendiente_recibir = fields.Monetary(
        string="MP pendiente de recibir",
        compute="_compute_resumen",
        currency_field="currency_id",
        help="Subtotal de POs vinculadas a OFs WIP (campo `fabricacion`) en estado purchase, pendientes de entregar (qty_received < product_qty).",
    )
    n_ofs_bom_incompleta = fields.Integer(
        string="OFs con BoM incompleta",
        compute="_compute_resumen",
        help="Nº de OFs donde el material real supera al teórico en >50%. Indica BoMs mal configuradas.",
    )
    total_mat_planned_ajustado = fields.Monetary(
        string="MP teórica ajustado",
        compute="_compute_resumen",
        currency_field="currency_id",
        help="Para OFs con BoM correcta usa el teórico de la BoM. Para OFs con BoM incompleta usa el real.",
    )
    total_cost_planned = fields.Monetary(string="Coste teórico total", compute="_compute_resumen", currency_field="currency_id")
    total_cost_real = fields.Monetary(string="Coste real total", compute="_compute_resumen", currency_field="currency_id")
    margen_estimado = fields.Monetary(string="Margen estimado", compute="_compute_resumen", currency_field="currency_id",
        help="Venta total - Coste teórico total. Es el margen esperado si todo va según plan.")
    grado_avance = fields.Float(string="Grado de avance", compute="_compute_resumen", digits=(16, 1),
        help="Coste real total / coste teórico total × 100. Avance económico global.")
    factor_global = fields.Float(string="Factor", compute="_compute_resumen", digits=(16, 2),
        help="Venta total / coste real. Objetivo JR: ≥ 1,35.")
    currency_id = fields.Many2one("res.currency", compute="_compute_resumen")

    def _ofs_domain(self, rec):
        if rec.modo == "historico":
            domain = [("state", "=", "done")]
            if rec.fecha_desde:
                domain.append(("date_finished", ">=", fields.Datetime.to_string(
                    fields.Date.from_string(str(rec.fecha_desde))
                )))
            if rec.fecha_hasta:
                hasta_dt = fields.Date.from_string(str(rec.fecha_hasta)) + timedelta(days=1)
                domain.append(("date_finished", "<", fields.Datetime.to_string(hasta_dt)))
            return domain
        return [("apunts_is_wip", "=", True)]

    @api.depends("modo", "fecha_desde", "fecha_hasta")
    @api.depends_context("uid")
    def _compute_resumen(self):
        Mo = self.env["mrp.production"]
        company_currency = self.env.company.currency_id
        for rec in self:
            wip = Mo.search(self._ofs_domain(rec))
            rec.n_ofs_wip = len(wip)
            rec.total_venta = sum(wip.mapped("apunts_sale_amount"))
            rec.total_mat_planned = sum(wip.mapped("apunts_mat_planned_total"))
            rec.total_mat_real = sum(wip.mapped("apunts_mat_real_total"))
            rec.total_mo_planned = sum(wip.mapped("apunts_mo_planned_total"))
            rec.total_mo_real = sum(wip.mapped("apunts_mo_real_total"))
            rec.total_machine_planned = sum(wip.mapped("apunts_machine_planned_total"))
            rec.total_machine_real = sum(wip.mapped("apunts_machine_real_total"))
            wip_ids = tuple(wip.ids) or (0,)
            self.env.cr.execute("""
                SELECT
                  COALESCE(SUM(wo.duration_expected), 0) AS min_plan,
                  COALESCE((
                      SELECT SUM(p.duration)
                      FROM mrp_workcenter_productivity p
                      JOIN mrp_workorder w ON w.id = p.workorder_id
                      WHERE w.production_id IN %s AND p.date_end IS NOT NULL
                  ), 0) AS min_real
                FROM mrp_workorder wo
                WHERE wo.production_id IN %s
            """, (wip_ids, wip_ids))
            row = self.env.cr.fetchone() or (0.0, 0.0)
            rec.total_min_planned = float(row[0] or 0.0)
            rec.total_min_real = float(row[1] or 0.0)
            rec.total_horas_planned = rec.total_min_planned / 60.0
            rec.total_horas_real = rec.total_min_real / 60.0
            rec.total_jornadas_planned = rec.total_horas_planned / 8.0
            rec.total_jornadas_real = rec.total_horas_real / 8.0
            rec.total_cost_planned = sum(wip.mapped("apunts_cost_total_planned"))
            rec.total_cost_real = sum(wip.mapped("apunts_cost_total_real"))
            rec.n_ofs_bom_incompleta = sum(1 for m in wip if m.apunts_bom_incompleta)
            rec.total_mat_planned_ajustado = sum(
                (m.apunts_mat_real_total if m.apunts_bom_incompleta else m.apunts_mat_planned_total)
                for m in wip
            )
            rec.margen_estimado = rec.total_venta - rec.total_cost_planned
            rec.grado_avance = (rec.total_cost_real / rec.total_cost_planned * 100.0) if rec.total_cost_planned else 0.0
            rec.factor_global = (rec.total_venta / rec.total_cost_real) if rec.total_cost_real else 0.0
            rec.currency_id = company_currency
            # MP pendiente de recibir: solo tiene sentido en modo en_curso
            if rec.modo == "historico":
                rec.total_mp_pendiente_recibir = 0.0
            else:
                POL = self.env["purchase.order.line"]
                if "fabricacion" in POL._fields and wip:
                    self.env.cr.execute("""
                        SELECT COALESCE(SUM(
                            (pol.product_qty - pol.qty_received) * pol.price_unit
                        ), 0)
                        FROM purchase_order_line pol
                        JOIN purchase_order po ON po.id = pol.order_id
                        WHERE pol.fabricacion IN %s
                          AND po.state IN ('purchase','done')
                          AND pol.qty_received < pol.product_qty
                    """, (wip_ids,))
                    row_mp = self.env.cr.fetchone() or (0.0,)
                    rec.total_mp_pendiente_recibir = float(row_mp[0] or 0.0)
                else:
                    rec.total_mp_pendiente_recibir = 0.0

    def action_open_lista_wip(self):
        return self.env.ref("apunts_jr_wip_costes_of.apunts_action_mrp_production_wip").read()[0]

    def action_open_lista_historico(self):
        action = self.env.ref("apunts_jr_wip_costes_of.apunts_action_mrp_production_wip").read()[0]
        action["name"] = "Historial OFs"
        domain = [("state", "=", "done")]
        if self.fecha_desde:
            domain.append(("date_finished", ">=", fields.Datetime.to_string(
                fields.Date.from_string(str(self.fecha_desde))
            )))
        if self.fecha_hasta:
            hasta_dt = fields.Date.from_string(str(self.fecha_hasta)) + timedelta(days=1)
            domain.append(("date_finished", "<", fields.Datetime.to_string(hasta_dt)))
        action["domain"] = domain
        action["context"] = {"search_default_filter_done": 1}
        return action

    def action_forzar_recompute(self):
        Mo = self.env["mrp.production"]
        mos = Mo.search([("state", "in", ("confirmed", "progress", "to_close"))])
        field = Mo._fields["apunts_is_wip"]
        self.env.add_to_compute(field, mos)
        self.env.flush_all()
        return self.action_open_resumen()

    @api.model
    def action_open_resumen(self):
        rec = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Resumen WIP",
            "res_model": "apunts.wip.resumen",
            "view_mode": "form",
            "view_id": self.env.ref("apunts_jr_wip_costes_of.apunts_wip_resumen_form").id,
            "res_id": rec.id,
            "target": "current",
        }
