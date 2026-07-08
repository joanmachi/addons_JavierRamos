{
    "name": "Apunts Taller Control (Bloqueos + Alertas Fichaje)",
    "summary": "Bloqueos automáticos de empleados en taller y alertas de fichajes anormales",
    "description": """
Apunts Taller Control
=====================

Cubre los puntos 3, 4, 7 y 8 del bloque "Sistema de fichaje y control de
operarios en taller":

3. Bloqueo automático tras 9 horas continuadas de fichaje en una OF
   (cron horario).
4. Bloqueo automático tras 5 minutos sin fichaje activo cuando el operario
   sigue checked-in en asistencia (cron cada 5 min).
7. Sentar las bases de "obligación de estar siempre fichado" mediante el
   bloqueo del punto 4 (sin fichaje activo > 5 min ⇒ bloqueado, debe
   pasar por oficina).
8. Detección de fichajes anormales > 16 horas: registra mensaje en el
   chatter de la orden de trabajo afectada y crea actividad para el
   responsable de fabricación.

El bloqueo se reflere en el empleado (`hr.employee.apunts_taller_bloqueado`).
Cuando un empleado está bloqueado:
- No puede iniciar nuevos fichajes en la vista taller (extensión de
  `mrp.production.iniciar_parar_orden`).
- No puede hacer toggle de asistencia (extensión de
  `hr.attendance.iniciar_taller_pin`).
- Solo se desbloquea desde la ficha del empleado por personal con
  permiso "Inventory / Manager" (botón "Desbloquear taller").

NO toca código existente; extiende los módulos `apunts_barcode_workorder`
y `javier_ramos_taller_simple`.

Punto pendiente del email cliente para futuras versiones:
- Punto 2 (botón "Salir" 14:00 con resumen): UI nueva.
- Punto 5 (sobre-fichaje controlado): wizard.
- Punto 6 (pregunta nº piezas obligatoria): ya existe parcialmente, validar.
- Punto 9 (vista master gestión oficina): requiere sesión con María José.
    """,
    "version": "18.0.2.4.0",
    "category": "Manufacturing",
    "author": "Apunts Informàtica",
    "website": "http://www.grupapunts.es",
    "license": "LGPL-3",
    "depends": [
        "mrp",
        "hr_attendance",
        "hr_holidays",
        "apunts_barcode_workorder",
        "javier_ramos_taller_simple",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/hr_employee_views.xml",
        "views/res_config_settings_views.xml",
        "wizards/fin_jornada_wizard_view.xml",
        "wizards/sobre_fichaje_wizard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "apunts_taller_control/static/src/js/qty_dialog_zero.js",
            "apunts_taller_control/static/src/js/fin_jornada_btn.js",
            "apunts_taller_control/static/src/js/sobre_fichaje_y_qty.js",
        ],
    },
    "installable": True,
    "application": False,
}
