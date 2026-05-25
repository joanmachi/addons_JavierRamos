from . import models


def _pre_init_uninstall_apunts_wip(env):
    """Marca apunts_wip para desinstalar: este módulo lo sustituye.

    No usamos button_immediate_uninstall porque no se puede en pre_init.
    button_uninstall solo marca el módulo (state='to remove'); el siguiente
    ciclo de Odoo lo procesa.
    """
    old = env["ir.module.module"].search([
        ("name", "=", "apunts_wip"),
        ("state", "=", "installed"),
    ])
    if old:
        old.button_uninstall()


def _post_init_recompute_wip(env):
    """Recompute caches WIP de OFs en curso tras instalar/actualizar.

    Sin esto, tras un upgrade los campos store=True heredan valores stale de la
    versión anterior hasta que alguien toque una purchase.order.line vinculada.
    """
    productions = env["mrp.production"].search([
        ("state", "in", ["confirmed", "progress", "to_close"]),
    ])
    if productions:
        productions._compute_apunts_wip_costs()
        productions._compute_apunts_minutos()
        productions._compute_apunts_partner_id()
        productions._compute_apunts_margen()
        productions._compute_apunts_sale_amount()
