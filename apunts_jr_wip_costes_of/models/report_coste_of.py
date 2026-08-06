# -*- coding: utf-8 -*-
from odoo import api, models


class ReportCosteOf(models.AbstractModel):
    _name = "report.apunts_jr_wip_costes_of.report_coste_of"
    _description = "Impresión del coste de OF"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Regenera las líneas de coste (igual que el botón 'Coste OF') para que
        el PDF muestre EXACTAMENTE los mismos números que la pantalla, y adjunta
        el detalle de material y mano de obra de cada OF."""
        productions = self.env["mrp.production"].browse(docids)
        Material = self.env["apunts.costes.of.material.line"]
        Labor = self.env["apunts.costes.of.labor.line"]
        material = {}
        labor = {}
        for prod in productions:
            prod._apunts_regenerate_lines()
            material[prod.id] = Material.search([("production_id", "=", prod.id)])
            labor[prod.id] = Labor.search([("production_id", "=", prod.id)])
        return {
            "doc_ids": docids,
            "doc_model": "mrp.production",
            "docs": productions,
            "material": material,
            "labor": labor,
        }
