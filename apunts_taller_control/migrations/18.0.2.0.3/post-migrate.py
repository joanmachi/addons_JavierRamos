def migrate(cr, version):
    """Setear ir.config_parameter con defaults razonables si no existen ya.

    bloqueo_inactividad_min: 30 (antes 5 hardcoded — evita bloqueos constantes).
    bloqueo_horas_continuas_of: 12 (antes 9 hardcoded — margen más amplio).
    Si ya existen (instalación limpia tras configurar), NO se sobreescriben.
    """
    defaults = [
        ("apunts_taller_control.bloqueo_inactividad_min", "30"),
        ("apunts_taller_control.bloqueo_horas_continuas_of", "12"),
    ]
    for key, value in defaults:
        cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s",
            (key,),
        )
        row = cr.fetchone()
        if row is None:
            cr.execute(
                "INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, "
                "create_date, write_date) "
                "VALUES (%s, %s, 1, 1, NOW(), NOW())",
                (key, value),
            )
