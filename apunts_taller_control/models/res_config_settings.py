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
        return res
