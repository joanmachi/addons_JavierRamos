# See LICENSE file for full copyright and licensing details.

from odoo import models


class Http(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """
        Inherit: Update the value of 'max_attachment_size' to the session. # T7329
        """
        session_info = super().session_info()
        IrConfigSudo = self.env["ir.config_parameter"].sudo()
        max_attachment_size = int(
            IrConfigSudo.get_param(
                "attachment_size_restriction.attachment_size_limit",
                default=10 * 1024 * 1024,  # 10 MB
            )
        )
        session_info.update({"max_attachment_size": max_attachment_size})
        return session_info
