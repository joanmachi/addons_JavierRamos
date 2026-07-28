# -*- coding: utf-8 -*-
from odoo import models


class ApuntsCostesOfMaterialLine(models.TransientModel):
    _inherit = "apunts.costes.of.material.line"

    def _compute_apunts_hija_id(self):
        """Extiende la detección de la OF hija: además del Origen automático
        (origin = nombre de la madre), reconoce el enlace manual
        (apunts_of_madre_manual_id apuntando a la madre). Así, al relacionar
        a mano una hija creada suelta, aparece el vínculo/botón 'Ver OF hija'
        en la pestaña Material, igual que el coste ya lo hace por el roll-up.
        """
        MO = self.env["mrp.production"]
        for line in self:
            hija = MO.browse()
            p = line.product_id
            of = line.production_id
            if p and p.bom_ids and of.name:
                hija = MO.search([
                    ("product_id", "=", p.id),
                    ("state", "!=", "cancel"),
                    "|",
                    ("origin", "=", of.name),
                    ("apunts_of_madre_manual_id", "=", of.id),
                ], order="id desc", limit=1)
            line.apunts_hija_id = hija
