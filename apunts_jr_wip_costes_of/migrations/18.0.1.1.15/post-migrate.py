# En v18.0.1.1.15 se cambia la fórmula de apunts_margen_pct (de × 100 a fracción 0..1
# para que widget="percentage" muestre el porcentaje correcto en pantalla) y la cascada
# del denominador en apunts_min_unit_real. Ambos campos son store=True, así que sin un
# recompute explícito los clientes quedarían con los valores viejos hasta el siguiente
# write en cada OF. Aquí recomputamos todas las OFs WIP de un golpe.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    productions = env["mrp.production"].search([
        ("state", "in", ["confirmed", "progress", "to_close"]),
    ])
    if productions:
        productions._compute_apunts_margen()
        productions._compute_apunts_minutos()
