🆕 GESTIÓN TALLER — CORRECCIONES, KPIs y PRESENCIA (18/06/2026)

Módulo: apunts_jr_gestion_taller.

T1 — Motivos de corrección como SELECTION + filtro (HECHO):
- En la corrección de fichajes (wizard corregir_fichaje_wizard) el motivo pasa a
  ser un selection con 3 opciones: 1) Falta OF  2) Responsabilidad operario
  3) Fuerza mayor.
- Filtros en "Histórico fichajes" para mostrar por cada motivo.

T2 — KPIs de fichadas: panel "KPIs de fichaje" en Gestión Taller con filtro de
  periodo, tarjetas (correcciones: % corregidos y por motivo; cumplimiento de
  jornada %) y tabla por empleado. (HECHO)

T3 — Nueva pestaña "Histórico presencia" en Gestión Taller (HECHO):
- Vista lista de presencias (hr.attendance) + ausencias (hr.leave) de los empleados.
- PDF tipo el de Asistencias (Reporte diario de registros) pero englobando
  presencias Y ausencias.

(Reposición/retrabajo + coste OF: HECHO en código, pendiente de validar en reunión.)


🆕 TABLETS EN PLANTA — DOCUMENTOS PDF DEL PRODUCTO EN LA TABLET (11/06/2026)

Objetivo: que cada estación de trabajo tenga una tablet (eliminar papeles).
En la vista de código de barras, al pulsar el NOMBRE DEL PRODUCTO fabricado se
abre un visor a pantalla completa con su(s) documento(s) PDF (ficha técnica,
planos, instrucciones).

Decisiones (reunión 11/06):
- Documentos: varios adjuntos (ir.attachment) por producto.
- Apertura: visor embebido a pantalla completa (no sale del kiosko).
- Alcance: solo el producto fabricado (no componentes, de momento).
- Tablets recomendadas: Android (el visor <iframe> de PDF va directo; iOS/Safari
  podría descargar en vez de mostrar → plan B pdf.js/pestaña).

Todo en el módulo apunts_barcode_workorder (no toca la lógica de fichaje).

- [ ] product.template: campo apunts_docs_taller_ids (Many2many ir.attachment)
      + pestaña "Documentos taller" en la ficha del producto (widget
      many2many_binary para subir varios).
- [ ] _get_stock_barcode_data: inyectar product_name + product_docs
      [{id,name,url:/web/content/<id>}].
- [ ] barcode_mrp_model.js: cargar product_name/product_docs + estado del visor
      (docVisorUrl) + abrirDoc()/cerrarDoc().
- [ ] main.xml: nombre del producto clickable (icono PDF) en cabecera Materiales;
      1 doc abre directo, varios → mini-lista; overlay visor con <iframe>.
- [ ] workorder.css: estilos del visor (reutiliza patrón apunts-zoom-overlay).
- [ ] Validar carga + probar en navegador; validar render PDF en la tablet real.


🆕 REVISIÓN REUNIÓN CLIENTE (10/06/2026) — CONTROL DE FICHAJE Y AUSENCIAS

Objetivo global: reforzar el control de que los operarios fichan correctamente
añadiendo un tercer tipo de bloqueo, integrando las AUSENCIAS justificadas en
todos los cálculos (para no penalizar médico/gestiones y para cuadrar con una
inspección de trabajo), mostrando esas ausencias al operario al cerrar jornada,
y dejando trazable en el histórico de fichajes qué se ha modificado y por qué.

──────────────────────────────────────────────────────────────────────────────
DECISIONES TOMADAS EN LA REUNIÓN (base del diseño)
──────────────────────────────────────────────────────────────────────────────
1. Fuente de horas para el cómputo de jornada/inspección:
   PRESENCIA (hr.attendance, entrada/salida) + AUSENCIAS aprobadas (hr.leave).
   Es lo que mira una inspección de trabajo. NO se usa la productividad de OFs
   para este cómputo (esa mide tiempo productivo, no presencia legal).
2. Umbral de horas mínimas: el del CALENDARIO del empleado
   (resource_calendar_id), no un número fijo. Soporta jornadas parciales y días
   no laborables (festivo/finde ⇒ 0h esperadas ⇒ nunca bloquea).
3. Seguimiento de correcciones: NO se crea modelo nuevo. Se añaden campos al
   propio HISTÓRICO DE FICHAJES (mrp.workcenter.productivity) y se hacen
   visibles y filtrables. Crear solo los campos que no existan.
4. Módulo de Ausencias (hr_holidays / "Tiempo personal"): CONFIRMADO instalado.
   Se añade a las dependencias y se lee hr.leave directamente.

──────────────────────────────────────────────────────────────────────────────
ESTADO ACTUAL DEL SISTEMA (lo que YA está hecho — punto de partida)
──────────────────────────────────────────────────────────────────────────────
Módulo apunts_taller_control:
  - models/taller_control.py: 3 crons
      · cron_alertar_fichajes_largos  → solo avisa fichajes >16h (no bloquea)
      · cron_bloquear_fichajes_largos → BLOQUEO 2: >N h continuas en OF (cfg, 12h)
      · cron_bloquear_inactividad     → BLOQUEO 1: >N min sin fichaje activo (cfg, 5')
  - models/res_config_settings.py: 2 parámetros configurables (min inactividad,
    horas continuas OF).
  - models/hr_employee.py: campos apunts_taller_bloqueado / _motivo_bloqueo /
    _fecha_bloqueo + action_apunts_desbloquear_taller (abre el wizard).
  - models/hr_attendance.py: iniciar_taller_pin() lanza error si está bloqueado.
  - data/cron_data.xml: definición de los 3 crons.
  - wizards/fin_jornada_wizard.py: resumen al cerrar jornada (SOLO productividad).
Módulo apunts_jr_gestion_taller:
  - wizards/corregir_fichaje_wizard.py: corrige/crea fichaje y desbloquea; el
    motivo se escribe SOLO en el chatter del empleado (message_post).
  - views/productivity_views.xml: "Histórico fichajes" (lista/search/pivot de
    mrp.workcenter.productivity). Aún SIN campos de modificación/motivo.

──────────────────────────────────────────────────────────────────────────────
PREREQUISITOS
──────────────────────────────────────────────────────────────────────────────
- [x] Añadir "hr_holidays" a depends de apunts_taller_control/__manifest__.py.
      Versión subida 18.0.2.0.5 → 18.0.2.1.0.
- [x] Confirmado en BD: TODOS los empleados activos usan el calendario id=1
      "Standard 40 hours/week" con flexible_hours=True, full_time_required=40,
      hours_per_day=8. Es FLEXIBLE (tienen calendario), no fully-flexible.
      Implicación: el calendario NO define días concretos (no hay franjas L-V),
      así que get_work_hours_count daría 8h hasta en sábado. ⇒ usamos
      hours_per_day como umbral y decidimos nosotros qué días son laborables
      (L-V, excluyendo festivos globales de resource.calendar.leaves).
      Fallback hours_per_day → 8h si faltara.

──────────────────────────────────────────────────────────────────────────────
BLOQUE A — NUEVO BLOQUEO 3: jornada insuficiente el día anterior
──────────────────────────────────────────────────────────────────────────────
Regla: bloquear al operario si el día laborable anterior fichó MENOS horas de
presencia (hr.attendance) de las esperadas por su calendario, descontando lo
cubierto por ausencias aprobadas.
   Cumplido = Σ presencia(hr.attendance del día) + Σ horas ausencia(hr.leave)
   Bloquear si  Cumplido < horas_esperadas_calendario(día) − tolerancia

- [x] Método cron_bloquear_jornada_insuficiente() en
      apunts_taller_control/models/taller_control.py:
      · esperadas = emp._apunts_horas_esperadas(ayer); 0 ⇒ saltar (finde/festivo).
      · cumplido = presencia + ausencias (helpers Bloque B).
      · bloquea si cumplido < esperadas − tolerancia. Motivo detallado.
      · Decisiones cliente: tolerancia configurable (default 10 min); 0h en día
        laborable SÍ bloquea; solo L-V.
- [x] Cron diario en data/cron_data.xml (nextcall 03:00, interval 1 día). El
      cron corre los 7 días; findes/festivos se descartan por esperadas=0, así
      cada día laborable se evalúa al día siguiente (sábado revisa viernes).
- [x] Parámetros en res_config_settings.py + vista de ajustes (junto a 5'/12h):
      · apunts_taller_bloqueo_jornada_activo (bool on/off, default on).
      · apunts_taller_jornada_tolerancia_min (minutos, default 10).
      · Umbral NO fijo: sale de hours_per_day del calendario del empleado.
- [x] Caso límite cubierto: si no hay jornada teórica (festivo/finde/sin
      calendario) ⇒ esperadas=0 ⇒ no se bloquea. (Media jornada: usaría su
      propio hours_per_day si lo tuviera; hoy todos son 8h.)

──────────────────────────────────────────────────────────────────────────────
BLOQUE B — AUSENCIAS: no penalizar y cuadrar con inspección (transversal)
──────────────────────────────────────────────────────────────────────────────
Las ausencias aprobadas (médico, llevar al hijo, etc.) deben SUMAR como tiempo
justificado en todos los cálculos de jornada. Mismo criterio que vería una
inspección: presencia + ausencias.

- [x] Helpers reutilizables en apunts_taller_control/models/hr_employee.py:
      · _apunts_horas_presencia(dia)  → Σ worked_hours de hr.attendance.
      · _apunts_horas_ausencia(dia)   → hr.leave state='validate'; por horas
        usa number_of_hours, por días completos imputa hours_per_day; tope a
        la jornada del día.
      · _apunts_es_dia_laborable(dia) → L-V y sin festivo global.
      · _apunts_horas_esperadas(dia)  → hours_per_day si laborable, else 0.
      · _apunts_tz / _apunts_rango_utc → día natural del empleado en UTC.
- [x] Usados en BLOQUE A (cron de bloqueo) y BLOQUE C (resumen fin de jornada).
- [ ] Revisar interacción con BLOQUEO 1 (>5 min sin fichaje activo): si el
      operario está de ausencia aprobada en ese momento, NO bloquear por
      inactividad. Añadir el check de ausencia activa en cron_bloquear_inactividad.
- [ ] (Opcional, a confirmar) PDF / vista "presencia + ausencias" por empleado
      y rango, para entregar en caso de inspección. Encaja con el pendiente ya
      existente "PDF para asistencias diarias".

──────────────────────────────────────────────────────────────────────────────
BLOQUE C — Mostrar ausencias en el resumen de FIN DE JORNADA (código de barras)
──────────────────────────────────────────────────────────────────────────────
Hoy el resumen al desfichar (apunts.fin.jornada.wizard._compute_resumen_html)
solo suma productividad de OFs. Debe mostrar también las ausencias del día.
Formato pedido: "Tiempo fichado Xh + X ausente".

- [x] fin_jornada_wizard.py / _compute_resumen_html:
      · Total combinado "X h fichadas + Y h ausencia = Z h" cuando hay ausencia.
      · Si hay ausencia pero ningún fichaje de producción, igualmente la muestra.
      · Sin ausencias ⇒ salida idéntica a la anterior.
- [x] DOBLE CONFIRMACIÓN al cerrar jornada (petición reunión, mejora):
      · action_confirmar_fin_jornada avisa si la jornada de HOY quedaría por
        debajo del mínimo que activa el bloqueo (misma base que el cron:
        presencia proyectada + ausencias < jornada − tolerancia).
        Proyecta la sesión de asistencia abierta hasta ahora.
      · 1ª pulsación de "Confirmar y salir" ⇒ muestra alerta roja ("vas a
        quedar bloqueado mañana, deberás pasar por oficina") y NO cierra.
      · 2ª pulsación (aviso_aceptado) ⇒ cierra igualmente.
      · Solo aplica si el bloqueo de jornada está activo y hoy es laborable.
- [ ] Verificar VISUALMENTE en la vista código de barras que el dialog de fin de
      jornada muestra bien el HTML (assets fin_jornada_btn.js/.xml) — pendiente
      de prueba en navegador con un operario con ausencia.

──────────────────────────────────────────────────────────────────────────────
BLOQUE D — Seguimiento de fichadas modificadas y motivos (en el histórico)
──────────────────────────────────────────────────────────────────────────────
Objetivo: poder ver qué empleados fallan a menudo en el fichaje (para darles
formación) filtrando por fichadas modificadas y por el motivo/comentario.
Decisión: campos en el propio histórico de fichajes, NO modelo nuevo.

- [x] Campos nuevos en mrp.workcenter.productivity
      (apunts_jr_gestion_taller/models/mrp_workcenter_productivity.py):
      · apunts_modificado_manual (Boolean, index) · apunts_motivo_correccion
        (Char) · apunts_modificado_por_id (res.users) · apunts_modificado_fecha.
- [x] Rellenados desde corregir_fichaje_wizard.py / action_aplicar:
      · CASO 1 (cerrar fichaje): marca el registro cerrado con motivo+usuario.
      · CASO 2 (crear fichaje): marca el registro creado con motivo+usuario.
      · Se mantiene el message_post en el chatter del empleado.
- [x] Vista histórico (apunts_jr_gestion_taller/views/productivity_views.xml):
      · Vista lista dedicada apunts_productivity_list_historico con columnas
        Modificado / Motivo / Modificado por / Fecha; decoración warning para
        filas modificadas; enlazada a la acción "Histórico fichajes".
      · Search: filtro "Modificados manualmente", búsqueda por motivo, agrupar
        por "Modificado manual". Columnas también disponibles en "fichados ahora".
- [x] Permisos: no requiere cambios (mismo modelo mrp.workcenter.productivity).

──────────────────────────────────────────────────────────────────────────────
ORDEN SUGERIDO DE IMPLEMENTACIÓN
──────────────────────────────────────────────────────────────────────────────
1) Prerequisitos (depends hr_holidays + verificar calendarios).
2) BLOQUE B (helper de ausencias) — base para A y C.
3) BLOQUE A (nuevo bloqueo) y ajuste anti-falsos-positivos del bloqueo 1.
4) BLOQUE C (resumen fin de jornada con ausencias).
5) BLOQUE D (trazabilidad en histórico).
6) Pruebas con casos reales (médico medio día, jornada parcial, festivo, sin
   desfichar) y subir versiones de manifest + migración si procede.


🔧 EN DESARROLLO / PROGRAMACIÓN

[PENDIENTE / A VIGILAR] Error de acceso "sale.order.line" al validar piezas desde la PDA
(usuario Planta id=7). Causa: campos calculados del WIP en mrp.production
(apunts_jr_wip_costes_of/models/mrp_production.py — apunts_sale_amount,
apunts_partner_id, margen…) leen sale_line_id -> sale.order.line; aunque son
store=True se recalculan en la transacción del operario al validar, y este no
tenía permiso de lectura sobre sale.order.line.
WORKAROUND aplicado (23/06/2026): se ha dado lectura a sale.order(.line) a los
grupos Fabricación/Usuario e Inventario/Usuario desde Ajustes (ir.model.access),
NO desde el módulo. A vigilar si resuelve el error en planta.
SI NO BASTA -> meter código: usar .sudo() en los _compute_ que leen sale_line_id
(opción de mínimo privilegio) y dejar la ACL solo en lectura. Revisar además que
la fila "sale.order.line manufacturing.user" no tenga write/create/unlink.

Corregir el PDF de entrega (albarán JR-SAL-00228) para que coincida con lo que se ve en pantalla - HECHO

Bloquear el cierre de jornada si hay OFs abiertas, mostrando mensaje de error con las OFs fichadas - HECHO

Ventana al desbloquear operario: selección de OF, tiempo sin fichar, imputación y motivo - HECHO

Corrección del doble fichaje: tiempo de operario dividido entre órdenes activas (no el 100%) - HECHO

Control de producción en curso — Puntos 2 y 3: sustituir "stock pronosticado" por stock / pendiente de entrega / entregado en la vista de producto - HECHO

Duración esperada de OF: multiplicar por unidades a producir (Fase1 60' + Fase2 180' × 9 uds) 
-------------

1.- Fichaje < Jornada laboral - Tolerancia = Bloqueo. HECHO

2.- Añadir resumen de las horas que lleva. (Horas presencia + horas ausencias). HECHO

3.- Doble verificación con aviso de ser bloqueado si no cumples el punto 1. HECHO

4.- Histórico de correcciones de los fichajes. HECHO

5.- Horarios de los empleados - Falta ver con Mª Jose.

6.- Añadir PDF del producto a producir en la vista de código de barras para poder añadir PDA. HECHO

7.- Ocultar las fases terminadas en la vista código de barras. HECHO

8.- Columna "Valor entregado" (uds. entregadas × precio unitario, sin dto. ni impuestos) en el DESGLOSE DE LÍNEAS DEL PEDIDO DE VENTA (sale.order.line). HECHO

9.- Informe por empleados: imprimir lista de empleados seleccionados con Nombre (operario) + Nº de identificación (DNI). Acción de impresión (binding) sobre hr.employee. HECHO

11.- Informe de fichadas/asistencias tipo "Reporte diario de registros" (CrossChex): seleccionar asistencias, agrupar por empleado y ordenar por fecha; por día mostrar fecha, día semana, hora entrada-salida, nº fichadas y horas trabajadas (working time). Acción de impresión (binding) sobre hr.attendance. HECHO (días sin fichaje no salen; pendiente si se quieren en blanco como CrossChex)

10.- Costes de la OF: coste REAL de materiales = cantidad CONSUMIDA en la OF (move_raw.quantity, lo usado) × precio del PEDIDO DE COMPRA vinculado (campo fabricacion). Cuenta lo usado (no lo comprado) y al precio de compra; fallback a coste estándar si el material no tiene PO. Solo materiales (MO y máquina sin tocar). HECHO



📅 PENDIENTE DE REUNIÓN

Aclarar columna "Albarán" que muestra números de OF — confirmar en qué vista aparece
Control de producción en curso — Punto 1: sesión presencial para explicar de dónde extrae cada cálculo el sistema
Explicar origen de datos (MO/MP) a Javi y Cynthia según categorías
Revisar discrepancia entre vista "Carga de Centro" y "Fabricación → Producción por Centro de Trabajo → Tabla"
Planificación y carga de trabajo: saneado general del apartado


✅ SOLUCIONADO

Pedido P00087 (Mafelec) — ya no aparece pendiente de facturar
Pedido P00116 (Stadler) — líneas abiertas cerradas
