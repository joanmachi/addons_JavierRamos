"""Pendientes de entrega: la columna qty_servible pasa a llamarse stock_a_mano;
se retira la antigua para no dejar basura en la tabla."""


def migrate(cr, version):
    cr.execute("ALTER TABLE lira_pending_delivery_line DROP COLUMN IF EXISTS qty_servible")
