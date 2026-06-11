# v18.0.1.1.22 (punto 10 JR): apunts_mat_real_total pasa a contar SOLO el coste
# comprado vía pedido de compra vinculado a la OF (campo `fabricacion`), valorado
# al precio del PO (importe recibido), sin mezclar el consumo físico ni el coste
# estándar del producto. Como material / coste total / margen son store=True,
# recomputamos todas las OFs WIP para que reflejen el nuevo criterio.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    productions = env["mrp.production"].search([
        ("state", "in", ["confirmed", "progress", "to_close"]),
    ])
    if productions:
        productions._compute_apunts_wip_costs()
        productions._compute_apunts_margen()
        # Forzar persistencia de los campos store=True antes del commit de la
        # migración (sin flush los valores recomputados no llegan a la BD).
        productions.flush_recordset()
