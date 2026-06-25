from odoo import fields, models

_WIP_FIELDS = [
    "apunts_is_wip",
    "apunts_mat_real_total",
    "apunts_cost_total_real",
    "apunts_cost_total_planned",
    "apunts_mat_planned_total",
    "apunts_mo_real_total",
    "apunts_machine_real_total",
    "apunts_mo_planned_total",
    "apunts_machine_planned_total",
    "apunts_bom_incompleta",
    "apunts_qty_pending",
    "apunts_mat_reposicion_extra",
]

_TRIGGER_FIELDS = {"qty_received", "fabricacion", "price_unit", "price_subtotal", "product_qty", "apunts_es_reposicion"}

_PRODUCT_COST_TRIGGER_FIELDS = {"qty_received", "price_unit", "price_subtotal", "product_id"}
_PRODUCT_COST_FIELDS = ["apunts_coste_real", "apunts_coste_fuente"]


def _product_ids_from_pols(pols):
    ids = set()
    for pol in pols:
        if pol.product_id:
            ids.add(pol.product_id.id)
    return ids


def _of_ids_from_pols(pols):
    ids = set()
    for pol in pols:
        fid = pol.fabricacion if isinstance(pol.fabricacion, int) else (
            pol.fabricacion.id if pol.fabricacion else None
        )
        if fid:
            ids.add(fid)
    return ids


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    apunts_es_reposicion = fields.Boolean(
        string="Compra por reposición",
        default=False,
        copy=False,
        index=True,
        help="Marca las líneas de compra generadas para REPONER piezas no validadas "
             "de una OF (refabricación). Su importe se suma al coste real de la OF como "
             "MP extra por reposición, y se EXCLUYE del precio de material consumido para "
             "no contar el coste dos veces.",
    )

    def write(self, vals):
        wip_triggered = bool(_TRIGGER_FIELDS.intersection(vals))
        product_cost_triggered = bool(_PRODUCT_COST_TRIGGER_FIELDS.intersection(vals))
        if not wip_triggered and not product_cost_triggered:
            return super().write(vals)

        of_ids_before = _of_ids_from_pols(self) if wip_triggered else set()
        new_fab = vals.get("fabricacion")
        if new_fab:
            of_ids_before.add(new_fab)
        product_ids_before = _product_ids_from_pols(self) if product_cost_triggered else set()

        result = super().write(vals)

        if wip_triggered:
            of_ids_after = _of_ids_from_pols(self)
            all_of_ids = of_ids_before | of_ids_after
            if all_of_ids:
                productions = self.env["mrp.production"].browse(list(all_of_ids)).exists()
                if productions:
                    productions.invalidate_recordset(_WIP_FIELDS)
                    productions._compute_apunts_wip_costs()

        if product_cost_triggered:
            product_ids_after = _product_ids_from_pols(self)
            all_product_ids = product_ids_before | product_ids_after
            if all_product_ids:
                products = self.env["product.product"].browse(list(all_product_ids)).exists()
                if products:
                    products.invalidate_recordset(_PRODUCT_COST_FIELDS)
                    products._compute_apunts_coste_real()

        return result

    def create(self, vals_list):
        records = super().create(vals_list)
        of_ids = _of_ids_from_pols(records)
        if of_ids:
            productions = self.env["mrp.production"].browse(list(of_ids)).exists()
            if productions:
                productions.invalidate_recordset(_WIP_FIELDS)
                productions._compute_apunts_wip_costs()
        product_ids = _product_ids_from_pols(records)
        if product_ids:
            products = self.env["product.product"].browse(list(product_ids)).exists()
            if products:
                products.invalidate_recordset(_PRODUCT_COST_FIELDS)
                products._compute_apunts_coste_real()
        return records
