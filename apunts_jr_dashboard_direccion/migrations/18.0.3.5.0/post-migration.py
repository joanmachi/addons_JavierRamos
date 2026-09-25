"""El margen de contribución desaparece de todas las pantallas (petición de la
empresa, 11-sep-2026): se retiran el KPI de la Reunión semanal con su histórico,
las fotos diarias, el objetivo y el criterio de semáforo."""


def migrate(cr, version):
    cr.execute("DELETE FROM apunts_kpi_serie WHERE clave = 'margen_bruto'")
    cr.execute("DELETE FROM apunts_kpi_semana WHERE clave = 'margen_bruto'")
    cr.execute("DELETE FROM apunts_kpi WHERE clave = 'margen_bruto'")
    cr.execute("DELETE FROM apunts_direccion_snapshot WHERE kpi IN ('margen_bruto', 'margen_bruto_pct')")
    cr.execute("DELETE FROM apunts_direccion_objetivo WHERE kpi = 'margen_bruto_pct'")
    cr.execute("DELETE FROM lira_ratio_criterio WHERE clave = 'margen_bruto'")
