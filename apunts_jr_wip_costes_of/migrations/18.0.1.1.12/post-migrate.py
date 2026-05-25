# Tras un upgrade los campos store=True heredan valores stale de la versión anterior
# hasta que alguien toque una purchase.order.line vinculada. Aquí recomputamos las OFs
# en curso de un golpe para que el cliente vea los valores correctos sin tener que
# pulsar "Forzar recompute" ni esperar al primer write.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    productions = env["mrp.production"].search([
        ("state", "in", ["confirmed", "progress", "to_close"]),
    ])
    if productions:
        productions._compute_apunts_wip_costs()
        productions._compute_apunts_minutos()
        productions._compute_apunts_partner_id()
        productions._compute_apunts_margen()
        productions._compute_apunts_sale_amount()
