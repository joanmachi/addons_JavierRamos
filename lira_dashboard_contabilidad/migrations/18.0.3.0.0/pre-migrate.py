# Rebrand 18.0.2.x → 18.0.3.0.0: módulo de contabilidad pierde los modelos de fabricación/WIP
# (lira.mrp.wip, lira.mrp.in.progress, lira.mrp.to.produce, lira.wip.valuation y sus *.line).
# Esos modelos viven ahora en apunts_jr_wip_costes_of. Aquí limpiamos las tablas físicas para
# evitar leftovers tras el upgrade. Odoo encargará de borrar las filas de ir.model / ir.model.fields
# automáticamente al detectar los modelos eliminados.


def migrate(cr, version):
    obsolete_tables = [
        "lira_mrp_wip_line",
        "lira_mrp_wip",
        "lira_mrp_in_progress_line",
        "lira_mrp_in_progress",
        "lira_mrp_to_produce_line",
        "lira_mrp_to_produce",
        "lira_wip_valuation_line",
        "lira_wip_valuation",
    ]
    for tbl in obsolete_tables:
        cr.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
