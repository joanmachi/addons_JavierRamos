"""Limpieza: columnas de una prueba descartada (coste real de OF en la ficha)
que solo existen en las BD locales. En producción no hay nada que quitar."""


def migrate(cr, version):
    cr.execute("ALTER TABLE product_template DROP COLUMN IF EXISTS lira_coste_of, DROP COLUMN IF EXISTS lira_coste_fuente, DROP COLUMN IF EXISTS lira_coste_auto")
    cr.execute("ALTER TABLE stock_quant DROP COLUMN IF EXISTS lira_valor_coste_of")
