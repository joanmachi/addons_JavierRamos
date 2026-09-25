"""El margen de contribución desaparece de todas las pantallas (petición de la
empresa): se retira su criterio de semáforo."""


def migrate(cr, version):
    cr.execute("DELETE FROM lira_ratio_criterio WHERE clave = 'margen_bruto'")
