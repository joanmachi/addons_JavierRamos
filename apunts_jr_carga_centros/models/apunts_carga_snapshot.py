import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApuntsCargaSnapshot(models.Model):
    """Foto diaria de la carga pendiente por centro de trabajo.

    La carga pendiente es una foto de "ahora": no se puede reconstruir
    con exactitud hacia atrás. Este modelo la persiste cada día (cron)
    para poder ver la EVOLUCIÓN (¿acumulamos retraso o vamos a mejor?).

    Para arrancar con historia, `generar_historico_estimado` reconstruye
    los últimos N días con una estimación (OTs creadas antes del día y no
    terminadas aún ese día, valoradas con su duración prevista actual).
    Esas filas quedan marcadas con `estimado=True`.
    """

    _name = "apunts.carga.snapshot"
    _description = "Foto diaria de carga pendiente por centro"
    _order = "fecha desc, workcenter_id"

    fecha = fields.Date(required=True, index=True)
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Centro",
        required=True,
        index=True,
        ondelete="cascade",
    )
    horas_pendientes = fields.Float(string="Horas pendientes")
    dias_pendientes = fields.Float(string="Días pendientes (8h)")
    n_workorders = fields.Integer(string="OTs abiertas")
    estimado = fields.Boolean(
        string="Estimado",
        help=(
            "True: fila reconstruida retroactivamente a partir de las fechas "
            "de creación/cierre de las OTs (estimación con la duración "
            "prevista actual). False: foto real tomada por el cron ese día."
        ),
    )

    _sql_constraints = [
        (
            "fecha_centro_uniq",
            "unique(fecha, workcenter_id)",
            "Ya existe una foto de ese centro para ese día.",
        )
    ]

    @api.model
    def cron_tomar_foto(self):
        """Foto real del día: sustituye cualquier fila previa del día
        (incluida una estimada) por el estado actual de cada centro."""
        hoy = fields.Date.context_today(self)
        self.search([("fecha", "=", hoy)]).unlink()
        centros = self.env["mrp.workcenter"].search([("active", "=", True)])
        vals = []
        for c in centros:
            vals.append(
                {
                    "fecha": hoy,
                    "workcenter_id": c.id,
                    "horas_pendientes": c.apunts_horas_pendientes,
                    "dias_pendientes": c.apunts_dias_pendientes,
                    "n_workorders": c.apunts_n_workorders_pendientes,
                    "estimado": False,
                }
            )
        if vals:
            self.create(vals)
        _logger.info(
            "Apunts carga snapshot: foto de %s tomada (%s centros).",
            hoy,
            len(vals),
        )

    @api.model
    def generar_historico_estimado(self, dias=90):
        """Reconstruye los últimos `dias` días SIN foto con una estimación:
        para cada día D, una OT estaba pendiente si se creó antes del fin
        de D y no estaba terminada a fin de D (por date_finished). Se
        valora con su duration_expected actual. No pisa fotos existentes.
        """
        hoy = fields.Date.context_today(self)
        creadas = 0
        for delta in range(dias, 0, -1):
            dia = hoy - timedelta(days=delta)
            if self.search_count([("fecha", "=", dia)]):
                continue
            fin_dia = datetime.combine(dia + timedelta(days=1), time.min)
            self.env.cr.execute(
                """
                SELECT wo.workcenter_id,
                       COALESCE(SUM(wo.duration_expected), 0) / 60.0,
                       COUNT(*)
                FROM mrp_workorder wo
                WHERE wo.workcenter_id IS NOT NULL
                  AND wo.create_date < %s
                  AND wo.state != 'cancel'
                  AND (wo.state != 'done' OR wo.date_finished >= %s)
                GROUP BY wo.workcenter_id
                """,
                (fin_dia, fin_dia),
            )
            vals = []
            for wc_id, horas, n_wo in self.env.cr.fetchall():
                vals.append(
                    {
                        "fecha": dia,
                        "workcenter_id": wc_id,
                        "horas_pendientes": float(horas or 0.0),
                        "dias_pendientes": float(horas or 0.0) / 8.0,
                        "n_workorders": int(n_wo or 0),
                        "estimado": True,
                    }
                )
            if vals:
                self.create(vals)
                creadas += len(vals)
        _logger.info(
            "Apunts carga snapshot: histórico estimado generado (%s filas).",
            creadas,
        )
        return creadas
