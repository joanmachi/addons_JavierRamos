# v18.0.1.5.0 (T1 reunión 18/06): apunts_motivo_correccion pasa de texto libre a
# Selection (falta_of / responsabilidad_operario / fuerza_mayor). Los motivos de
# texto libre antiguos no son claves válidas del selection: se ponen a NULL para
# que el campo quede limpio (quedan "sin clasificar", como acordado).


def migrate(cr, version):
    cr.execute("""
        UPDATE mrp_workcenter_productivity
           SET apunts_motivo_correccion = NULL
         WHERE apunts_motivo_correccion IS NOT NULL
           AND apunts_motivo_correccion NOT IN
               ('falta_of', 'responsabilidad_operario', 'fuerza_mayor')
    """)
