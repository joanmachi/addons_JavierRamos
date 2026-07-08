from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    apunts_taller_bloqueo_inactividad_min = fields.Integer(
        string="Minutos sin fichaje activo para bloquear",
        default=30,
        help=(
            "Bloquear operario si lleva X minutos checked-in en asistencia "
            "sin ningún fichaje activo en ninguna orden. "
            "Pon 0 para desactivar este bloqueo."
        ),
    )
    apunts_taller_bloqueo_horas_continuas_of = fields.Integer(
        string="Horas continuas en OF para bloquear",
        default=12,
        help=(
            "Bloquear operario si lleva más de X horas continuas fichado "
            "en la misma orden de fabricación. "
            "Pon 0 para desactivar este bloqueo."
        ),
    )
    apunts_taller_bloqueo_jornada_activo = fields.Boolean(
        string="Bloquear por jornada insuficiente el día anterior",
        default=True,
        help=(
            "Bloquear al operario si el día laborable anterior (L-V, sin "
            "festivos) la suma de presencia (asistencia) + ausencias aprobadas "
            "no alcanza la jornada de su calendario, descontando la tolerancia. "
            "Desmarca para desactivar este bloqueo."
        ),
    )
    apunts_taller_jornada_tolerancia_min = fields.Integer(
        string="Tolerancia jornada insuficiente (min)",
        default=10,
        help=(
            "Margen en minutos por debajo de la jornada teórica antes de "
            "bloquear. Ej: jornada 8h y tolerancia 10 ⇒ bloquea si fichó menos "
            "de 7h50m (presencia + ausencias)."
        ),
    )

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "apunts_taller_control.bloqueo_inactividad_min",
            str(self.apunts_taller_bloqueo_inactividad_min),
        )
        ICP.set_param(
            "apunts_taller_control.bloqueo_horas_continuas_of",
            str(self.apunts_taller_bloqueo_horas_continuas_of),
        )
        ICP.set_param(
            "apunts_taller_control.bloqueo_jornada_activo",
            "1" if self.apunts_taller_bloqueo_jornada_activo else "0",
        )
        ICP.set_param(
            "apunts_taller_control.jornada_tolerancia_min",
            str(self.apunts_taller_jornada_tolerancia_min),
        )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res["apunts_taller_bloqueo_inactividad_min"] = int(
            ICP.get_param("apunts_taller_control.bloqueo_inactividad_min", "30")
        )
        res["apunts_taller_bloqueo_horas_continuas_of"] = int(
            ICP.get_param("apunts_taller_control.bloqueo_horas_continuas_of", "12")
        )
        res["apunts_taller_bloqueo_jornada_activo"] = (
            ICP.get_param("apunts_taller_control.bloqueo_jornada_activo", "1") == "1"
        )
        res["apunts_taller_jornada_tolerancia_min"] = int(
            ICP.get_param("apunts_taller_control.jornada_tolerancia_min", "10")
        )
        return res
