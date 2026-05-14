# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Added a new field # T7329
    max_file_attachment_size = fields.Integer(
        string="Maximum File Size",
        help="Set the file size in Byte.",
        config_parameter="attachment_size_restriction.attachment_size_limit",
    )
