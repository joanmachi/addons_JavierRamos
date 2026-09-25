# Registro de modificaciones - Odoo 18 Javier Ramos

---

## [001] Columna Fecha Vencimiento en lista de facturas

**Fecha:** 2026-05-14  
**Módulo:** `javier_ramos_pedidos`  
**Ficheros modificados:**
- `javier_ramos_pedidos/views/factura.xml` — vista lista (record id: `account_move_tree_view_inherit_date_due`)
- `javier_ramos_pedidos/models/account_move.py` — campo relacionado `invoice_due_date_display`
- `javier_ramos_pedidos/models/__init__.py` — import del nuevo modelo

**Vista afectada:** Contabilidad > Facturas y Contabilidad > Facturas de proveedores (lista)

**Qué hace:**  
Añade una columna "Fecha Vencimiento" en formato fecha junto a la columna existente de días restantes (`remaining_days`). Usa un campo relacionado `invoice_due_date_display` → `invoice_date_due` para poder mostrar ambas columnas a la vez.

**Para aplicar cambios:**
```
docker exec odoo_javierramos_local-odoo-1 odoo -d javierramoslocal --update=javier_ramos_pedidos --stop-after-init
docker restart odoo_javierramos_local-odoo-1
```

---

## [002] Corrección campo invoice_due_date_display — store=True

**Fecha:** 2026-05-14  
**Módulo:** `javier_ramos_pedidos`  
**Ficheros modificados:**
- `javier_ramos_pedidos/models/account_move.py` — añadido `store=True` al campo relacionado

**Por qué:**  
Al intentar actualizar el módulo, Odoo rechazaba la vista con el error *"El campo invoice_due_date_display no existe en el modelo account.move"*. Odoo valida las vistas contra los campos registrados en la BD; un campo `related` con `store=False` no siempre se reconoce durante la fase de validación de vistas en una actualización. Con `store=True` el campo queda registrado como columna y la validación pasa sin error.

---

## [003] Albarán valorado — nueva acción de impresión

**Fecha:** 2026-05-14  
**Módulos modificados:** `stock_picking_report_valued`  
**Ficheros modificados:**
- `stock_picking_report_valued/report/stock_picking_report_valued.xml` — añadido `ir.actions.server` con `binding_type='report'` + variable `show_valued` en template
- `stock_picking_report_valued/models/stock_picking.py` — añadido método `action_print_valued_albaran()`

**Por qué:**  
El módulo OCA `stock_picking_report_valued` muestra precios en el albarán solo si el partner tiene `valued_picking=True`. El usuario necesitaba que cualquier empleado pudiera elegir imprimir la versión con o sin precios en el momento de imprimir, sin depender de la configuración del partner.

**Solución adoptada:**

1. Se añade una `ir.actions.server` con `binding_type='report'` vinculada a `stock.picking` para que aparezca en el menú **Imprimir** del albarán bajo el nombre *"Imprimir Albarán Valorado"*.

2. El server action llama al método Python `action_print_valued_albaran()`, que usa `with_context(force_valued=True)` antes de `report_action()`. El contexto es el único mecanismo que Odoo propaga correctamente hasta el template QWeb en el ciclo server action → frontend → descarga PDF (`ir.actions.report` no tiene campo `context` en Odoo 18, y el dict `data=` de `report_action` no llega al template por cómo se serializa la petición de descarga).

3. En el template, se sustituye el uso directo de `o.valued` por una variable `show_valued` que combina ambas condiciones:
   ```xml
   <t t-set="show_valued" t-value="o.valued or o.env.context.get('force_valued', False)" />
   ```
   Así, la lógica original del partner sigue funcionando y el flag de contexto activa siempre la versión valorada.

**Intentos descartados durante el desarrollo:**
- `<field name="context">` en `ir.actions.report` → campo no existe en Odoo 18
- `report_action(self, data={'force_valued': True})` + `data.get()` en template → el dict `data` no llega al template porque el frontend reconstruye la URL de descarga sin incluirlo
- `ir.actions.report._get_report('stock.report_delivery_document')` → ese XML ID es un `ir.ui.view` (template QWeb), no un `ir.actions.report`; el ID correcto de la acción es `stock.action_report_delivery`

---

## [004] Corrección tabla duplicada en albarán — apunts_stock_delivery_grouped

**Fecha:** 2026-05-14  
**Módulo:** `apunts_stock_delivery_grouped`  
**Ficheros modificados:**
- `apunts_stock_delivery_grouped/views/report_delivery_grouped.xml` — añadido `t-if` de estado en las tablas reemplazadas

**Por qué:**  
El albarán imprimía la tabla de productos dos veces. El módulo `apunts_stock_delivery_grouped` usa `position="replace"` para sustituir las dos tablas del template base de Odoo (`stock_move_table` para albaranes pendientes y `stock_move_line_table` para albaranes validados). En Odoo 18, la condición `t-if` que controla qué tabla mostrar según el estado está en el propio elemento `<table>`, no en un wrapper externo. Al hacer `replace`, se sustituye el elemento completo incluyendo ese `t-if`, y ambas tablas quedaban sin condición y se mostraban siempre.

**Solución:** añadir de nuevo las condiciones en las tablas reemplazadas:
- `stock_move_table` → `t-if="o.state != 'done'"`
- `stock_move_line_table` → `t-if="o.state == 'done'"`

---

## [005] Supervisor Planta — clic en fila abre la orden de fabricación

**Fecha:** 2026-05-14  
**Módulo:** `lira_mfg_supervisor`  
**Ficheros modificados:**
- `lira_mfg_supervisor/models/lira_supervisor_workorder.py` — método `action_open_production()`
- `lira_mfg_supervisor/static/src/js/supervisor_list.js` — nuevo componente OWL `lira_supervisor_list`
- `lira_mfg_supervisor/views/lira_supervisor_views.xml` — `js_class="lira_supervisor_list"` en ambas vistas lista
- `lira_mfg_supervisor/__manifest__.py` — registro del JS en `web.assets_backend`

**Por qué:**  
El panel del supervisor muestra filas de `mrp.workorder`. Al hacer clic, Odoo abría (o intentaba abrir) el formulario del workorder, que no es útil en el contexto de supervisión. El usuario necesitaba que el clic navegara directamente a la orden de fabricación (`mrp.production`) relacionada.

**Solución adoptada:**

1. Se añade el método Python `action_open_production()` que devuelve una `ir.actions.act_window` apuntando al formulario de `mrp.production` con el `res_id` de `self.production_id`.

2. Se crea `supervisor_list.js` con un componente OWL `SupervisorListController` que extiende `ListController` y sobreescribe `openRecord(record)` para llamar al método Python en lugar de abrir el workorder. Se registra como vista personalizada `lira_supervisor_list`.

3. Se añade `js_class="lira_supervisor_list"` a las dos vistas lista del módulo (Panel en tiempo real e Historial del día) para que ambas usen el controlador personalizado.

**Error encontrado durante el desarrollo:**  
`TypeError: Cannot read properties of undefined (reading 'call')` — `this.orm` era `undefined` al sobreescribir `openRecord` sin definir `setup()`. En OWL 2, los hooks de `useService` deben llamarse explícitamente en el `setup()` del componente que los usa. La solución fue definir `setup()` en el subcomponente, llamar a `super.setup()` y registrar los servicios propios (`this._orm`, `this._action`) con `useService`, en lugar de depender de los heredados del padre.

---

## [006] Etiquetas albarán — corrección formato y maquetación

**Fecha:** 2026-05-15  
**Módulo:** `javier_ramos_taller_simple`  
**Ficheros modificados:**
- `javier_ramos_taller_simple/report/paper_format.xml` — definidas dimensiones reales de la etiqueta (150 × 105 mm)
- `javier_ramos_taller_simple/report/labels.xml` — reescritura completa de las plantillas de etiqueta
- `javier_ramos_taller_simple/views/pedidos.xml` — comentado xpath que referenciaba campo Studio eliminado

**Vista afectada:** Inventario > Traslados > imprimir etiquetas de albarán (recepción y expedición)

**Qué hace:**
Corrige dos problemas en las etiquetas de albarán:

1. **Logo flotante a mitad de la etiqueta**: causado por `web.internal_layout`, que inserta un header con posición fija y el logo de empresa. En etiquetas pequeñas (150 × 105 mm) ese header se superpone al contenido. Se eliminó el `t-call="web.internal_layout"` y el template `internal_layout_inherit`. Las plantillas ahora usan directamente `<div class="page">` con tabla CSS en línea.

2. **Contenido desbordando la página**: causado por `font-size: 3rem` (demasiado grande) + 7 `<br/>` de margen superior + dimensiones de papel no definidas (`page_height=0`, `page_width=0`). Se corrigió: `page_height=150`, `page_width=105`, fuente 9pt / cabecera 11pt, eliminados todos los `<br/>` innecesarios.

3. **Tipo de código de barras**: cambiado de `EAN13` (requiere formato numérico estricto) a `Code128` (acepta cualquier cadena alfanumérica).

4. **Logo reposicionado**: ahora aparece como última fila de la tabla de contenido, en la parte inferior de la etiqueta.

5. **Vista `pedidos.xml`**: se comentó el xpath `//field[@name='x_studio_rdenes_de_fabricacin']` que referenciaba un campo Studio que ya no existe en la vista padre de `sale.order`, lo que impedía la actualización del módulo.

**Para aplicar cambios:**
```
docker exec odoo_javierramos_local-odoo-1 odoo -d javierramoslocal --update=javier_ramos_taller_simple --stop-after-init
docker restart odoo_javierramos_local-odoo-1
```

---

## [007] Etiquetas albarán — versión mejorada final (logo arriba, barcodes, divisores)

**Fecha:** 2026-05-16  
**Módulo:** `javier_ramos_taller_simple`  
**Ficheros modificados:**
- `javier_ramos_taller_simple/report/labels.xml` — reescritura completa del diseño
- `javier_ramos_taller_simple/report/paper_format.xml` — ajuste a 150×105 mm, dpi=96

**Qué hace:**  
Versión final del diseño de etiqueta de albarán:
- Logo de empresa centrado en la parte superior (fuera del recuadro)
- Recuadro con borde exterior desde la cabecera hasta el final
- Cabecera gris oscuro (#555555) con título centrado y número de traslado en esquina derecha
- Dos columnas de barcodes (ARTICULO | ORDEN) con separador vertical `bgcolor="#cccccc"`
- Secciones de contenido como `<div>` independientes para evitar bordes Bootstrap
- Etiqueta en gris pequeño arriba, valor en negrita abajo (FECHA ENTREGA, PEDIDO JR, Nº PEDIDO CLIENTE)
- CANTIDAD | LONGITUD con separador vertical al final
- `class="page article"` en el div de página para correcto charset UTF-8 en `_prepare_html`
- `dpi=96` en paper_format (zoom=1.0); con dpi=203 el contenido aparecía al 47%

**Para aplicar cambios:**
```
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal --update javier_ramos_taller_simple --stop-after-init
docker compose start odoo
```

---

## [008] Recuperar fecha vencimiento y clic supervisor tras merge Alex v1

**Fecha:** 2026-05-19  
**Módulos:** `javier_ramos_pedidos`, `lira_mfg_supervisor`  
**Ficheros modificados:**
- `javier_ramos_pedidos/views/factura.xml` — restaurado record `account_move_tree_view_inherit_date_due`
- `javier_ramos_pedidos/models/account_move.py` — restaurado campo `invoice_due_date_display`
- `javier_ramos_pedidos/models/__init__.py` — restaurado import de `account_move`
- `lira_mfg_supervisor/models/lira_supervisor_workorder.py` — restaurado `action_open_production()`
- `lira_mfg_supervisor/views/lira_supervisor_views.xml` — restaurado `js_class="lira_supervisor_list"`
- `lira_mfg_supervisor/static/src/js/supervisor_list.js` — restaurado componente OWL
- `lira_mfg_supervisor/__manifest__.py` — restaurado `supervisor_list.js` en assets

**Por qué:**  
El merge de la carpeta addons de Alex (primera entrega) sobrescribió las modificaciones [001] y [005]. Se recuperaron todas las funcionalidades sobre la base de Alex.

---

## [009] Comentar xpath Studio en pedidos.xml

**Fecha:** 2026-05-19  
**Módulo:** `javier_ramos_taller_simple`  
**Ficheros modificados:**
- `javier_ramos_taller_simple/views/pedidos.xml`

**Por qué:**  
El xpath `//field[@name='x_studio_rdenes_de_fabricacin']` referencia un campo Studio eliminado de la vista padre `sale.view_order_form` en producción. Dejarlo activo impide actualizar el módulo. Se comenta con nota explicativa para no perderlo en futuros merges.

---

## [010] lira_mfg_supervisor: versión exacta de Alex (gestión de merge)

**Fecha:** 2026-05-20  
**Módulo:** `lira_mfg_supervisor`  
**Nota:** Commit de gestión — se reemplazaron los ficheros del módulo por la versión exacta del compañero Alex tal como está en producción, para partir desde una base limpia antes de aplicar las modificaciones propias.

---

## [011] lira_mfg_supervisor: clic en fila abre orden de fabricación

**Fecha:** 2026-05-20  
**Módulo:** `lira_mfg_supervisor`  
**Ficheros modificados:**
- `lira_mfg_supervisor/models/lira_supervisor_workorder.py` — método `action_open_production()`
- `lira_mfg_supervisor/static/src/js/supervisor_list.js` — componente OWL `SupervisorListController`
- `lira_mfg_supervisor/views/lira_supervisor_views.xml` — `js_class="lira_supervisor_list"`
- `lira_mfg_supervisor/__manifest__.py` — JS añadido a assets

**Qué hace:**  
Al hacer clic en cualquier fila del Panel Supervisor, navega directamente al formulario de la orden de fabricación (`mrp.production`) en lugar de abrir el workorder.

---

## [012] Fix action_open_production: añadir `views` para _preprocessAction

**Fecha:** 2026-05-20  
**Módulo:** `lira_mfg_supervisor`  
**Ficheros modificados:**
- `lira_mfg_supervisor/models/lira_supervisor_workorder.py`

**Por qué:**  
El clic lanzaba `TypeError: Cannot read properties of undefined (reading 'map')` en el frontend. En Odoo 18, `_preprocessAction` del cliente JS requiere que el dict de acción incluya la clave `views`. Sin ella, el método intenta hacer `.map()` sobre `undefined`.

**Solución:** añadir `'views': [(False, 'form')]` al dict devuelto por `action_open_production()`.

---

## [013] Estado addons Alex v2 — segunda entrega (gestión de merge)

**Fecha:** 2026-05-26  
**Nota:** Commit de gestión — integración de la segunda carpeta addons de Alex. Cambios relevantes:
- Nuevo módulo instalado: `apunts_jr_parciales_of`
- Módulos eliminados del repo: `apunts_stock_delivery_grouped`, `apunts_wip`
- Eliminado por Alex: `javier_ramos_pedidos/models/account_move.py` (restaurado en [014])
- Eliminado por Alex: `lira_mfg_supervisor/static/src/js/supervisor_list.js` (restaurado en [014])

---

## [014] Restaurar customizaciones sobre Alex v2

**Fecha:** 2026-05-26  
**Módulos:** `javier_ramos_pedidos`, `javier_ramos_taller_simple`, `lira_mfg_supervisor`  
**Ficheros modificados:**
- `javier_ramos_taller_simple/views/pedidos.xml` — xpath Studio comentado de nuevo
- `javier_ramos_taller_simple/report/labels.xml` — restaurado diseño mejorado [007]
- `javier_ramos_taller_simple/report/paper_format.xml` — restaurado 150×105mm, dpi=96
- `javier_ramos_pedidos/models/account_move.py` — recreado con `invoice_due_date_display`
- `javier_ramos_pedidos/models/__init__.py` — reimportado `account_move`
- `javier_ramos_pedidos/views/factura.xml` — restaurada columna Fecha Venc.
- `lira_mfg_supervisor/models/lira_supervisor_workorder.py` — restaurado `action_open_production()`
- `lira_mfg_supervisor/views/lira_supervisor_views.xml` — restaurado `js_class="lira_supervisor_list"`
- `lira_mfg_supervisor/static/src/js/supervisor_list.js` — recreado componente OWL
- `lira_mfg_supervisor/__manifest__.py` — JS restaurado en assets

**Por qué:**  
La segunda entrega de Alex sobrescribió todas las modificaciones propias. Se restauraron íntegramente sobre la nueva base.

---

## [015] README: workflow para Alex, prompt para Claude, estado módulos

**Fecha:** 2026-05-26  
**Ficheros modificados:**
- `README.md`

**Qué hace:**  
Actualización completa del README con el estado real de los módulos, instrucciones para que Alex pueda clonar el repo e integrar los cambios en su entorno Mac, y un prompt listo para copiar-pegar a su Claude Code.

---

## [016] Desglose líneas de venta y factura

**Fecha:** 2026-05-27  
**Módulo:** `javier_ramos_pedidos`  
**Ficheros modificados:**
- `javier_ramos_pedidos/models/pedido_linea.py` — campo `qty_to_deliver` (pendiente de entrega)
- `javier_ramos_pedidos/views/desglose_ventas.xml` — nuevo fichero con ambas vistas
- `javier_ramos_pedidos/__manifest__.py` — añadido `desglose_ventas.xml`

**Vista afectada:**
- Ventas > Informes > Desglose líneas de venta
- Contabilidad > Informes > Desglose líneas de factura

**Qué hace:**  
Dos vistas lista independientes para analizar el estado de cada línea sin entrar en cada pedido o factura:

**Desglose líneas de venta** (`sale.order.line`):
- Columnas: Pedido, Cliente, Producto, Pedido (qty), Entregado, Pdte. entrega (rojo si > 0), Facturado, Estado, Subtotal
- Sumas totales por columna numérica
- Filtros: *Pendiente de entregar* / *Entregado y pendiente de facturar* / *Completamente facturado* / *Solo pedidos confirmados*
- Agrupaciones por: Cliente, Producto, Pedido, Estado facturación

**Desglose líneas de factura** (`account.move.line`):
- Solo líneas de producto de facturas de cliente (excluye impuestos, subtotales, etc.)
- Columnas: Fecha, Factura, Cliente, Producto, Cantidad, Precio, Subtotal, Estado
- Filtros: *Facturas confirmadas* / *Borradores* / *Este mes*
- Agrupaciones por: Cliente, Producto, Factura, Mes

**Para aplicar cambios:**
```
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal --update javier_ramos_pedidos --stop-after-init
docker compose start odoo
```

---

## [017] Coste cadena OFs parciales — smart button en apunts_jr_parciales_of

**Fecha:** 2026-05-27  
**Módulo:** `apunts_jr_parciales_of`  
**Ficheros modificados/creados:**
- `apunts_jr_parciales_of/models/apunts_jr_costes_cadena.py` — nuevo TransientModel `apunts.jr.costes.cadena`
- `apunts_jr_parciales_of/models/mrp_production.py` — nuevos campos `jr_is_parcial`, `jr_cadena_count` y método `action_jr_costes_cadena()`
- `apunts_jr_parciales_of/models/__init__.py` — import del nuevo modelo
- `apunts_jr_parciales_of/security/ir.model.access.csv` — acceso al TransientModel
- `apunts_jr_parciales_of/views/apunts_jr_costes_cadena_views.xml` — vista formulario con KPIs + tabla desglose + lista OFs
- `apunts_jr_parciales_of/views/mrp_production_views.xml` — smart button en button_box
- `apunts_jr_parciales_of/__manifest__.py` — nuevos ficheros en `data`

**Módulo eliminado:** `javier_ramos_costes_of` (eliminado carpeta + limpieza BD)

**Vista afectada:**  
Fabricación > Orden de fabricación (formulario) — aparece el botón "Coste cadena" con el número de OFs cuando la OF es parcial (pertenece a una cadena de más de una OF).

**Qué hace:**  
Al clicar el smart button "Coste cadena" en una OF parcial, abre una vista con:
- 4 tarjetas KPI: Venta total (verde), En curso real (ámbar), Coste teórico (azul), Margen actual (verde/ámbar/rojo según umbral 20%/0%)
- Tabla desglose: MP, Tiempo, Coste operario, Coste máquina, TOTAL — columnas Teórico vs Real
- Lista de todas las OFs de la cadena con sus costes individuales y sumas por columna

Los costes se agregan sumando los campos `apunts_*` de todas las OFs hermanas (misma `procurement_group_id`). La venta se calcula también por suma (distribución proporcional de `sale_line_id`).

**Para aplicar cambios:**
```
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal --update apunts_jr_parciales_of --stop-after-init
docker compose start odoo
```

---

## [018] Factor de cobertura (venta / coste real)

**Fecha:** 2026-05-27  
**Módulos:** `apunts_jr_wip_costes_of`, `apunts_jr_parciales_of`  
**Ficheros modificados:**
- `apunts_jr_wip_costes_of/models/mrp_production.py` — nuevo campo `apunts_factor_cobertura` (Float, 2 dec.) calculado en `_compute_apunts_margen`
- `apunts_jr_wip_costes_of/views/apunts_costes_of_redesign.xml` — muestra el factor en la tarjeta "Margen actual" de la vista Coste OF
- `apunts_jr_wip_costes_of/views/mrp_production_views.xml` — columna `Factor (×)` opcional en la lista WIP
- `apunts_jr_parciales_of/models/apunts_jr_costes_cadena.py` — campo `cadena_factor_cobertura`
- `apunts_jr_parciales_of/models/mrp_production.py` — cálculo del factor en `action_jr_costes_cadena`
- `apunts_jr_parciales_of/views/apunts_jr_costes_cadena_views.xml` — muestra el factor en la tarjeta "Margen actual" de la vista Coste cadena

**Qué hace:**  
Añade el indicador `Factor = Venta / Coste real` en los tres sitios donde se muestran costes de OFs. Objetivo JR: ≥ 1,35.

- Verde: factor ≥ 1,35 (objetivo cumplido)
- Ámbar: 1,0 ≤ factor < 1,35 (rentable pero por debajo del objetivo)
- Rojo: factor < 1,0 (pérdidas)
- Sin color: factor = 0 (OF sin datos de coste real todavía)

Si la OF no tiene fichajes reales (coste_real = 0), muestra 0 sin colorear.

**Para aplicar cambios:**
```
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal --update apunts_jr_wip_costes_of,apunts_jr_parciales_of --stop-after-init
docker compose start odoo
```

---

## [019] Fix bug presupuesto desde OF — display_qty_widget

**Fecha:** 2026-05-27  
**Módulo:** `javier_ramos_pedidos`  
**Ficheros modificados:**
- `javier_ramos_pedidos/models/pedido_linea.py` — eliminado método `_compute_qty_to_deliver` propio y simplificado campo `qty_to_deliver`

**Por qué:**  
Al abrir un presupuesto desde una OF salía `ValueError: Compute method failed to assign sale.order.line(...).display_qty_widget`. El módulo definía su propio `_compute_qty_to_deliver` que solo asignaba `qty_to_deliver` pero machacaba el método de `sale_stock`, que también asigna `display_qty_widget`. Al no asignar ese campo, Odoo lanzaba el error.

**Solución:** eliminar el método custom y dejar solo `qty_to_deliver = fields.Float(string='Pdte. entrega')` para conservar el label en español sin interferir con el método de `sale_stock`.

---

## [020] Columna "Fecha entrega" en Pedidos Pendientes de Entrega

**Fecha:** 2026-06-02  
**Módulo:** `lira_dashboard_contabilidad`  
**Ficheros modificados:**
- `lira_dashboard_contabilidad/models/lira_pending_delivery.py` — campo `fecha_entrega` en `LiraPendingDeliveryLine`; poblado desde `sale.order.commitment_date` en `_build_data`
- `lira_dashboard_contabilidad/views/lira_pending_delivery_views.xml` — columna `fecha_entrega` entre `fecha_pedido` y `partner_id`, con `decoration-danger` para fechas vencidas

**Qué hace:**  
En la vista "Pedidos pendientes de entrega — detalle" aparece la columna **Fecha entrega** (fecha comprometida con el cliente) sin tener que abrir el pedido. Las filas con fecha ya vencida se colorean en rojo.

**Para aplicar cambios:**
```
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal --update lira_dashboard_contabilidad --stop-after-init
docker compose start odoo
```

---

## [021] Prorrateo de coste de centro y mano de obra en solapamientos de OFs

**Fecha:** 2026-06-04  
**Módulos:** `apunts_costes_of` (11.2.0) · `apunts_jr_wip_costes_of` (1.1.20)  
**Ficheros modificados:**
- `apunts_costes_of/models/mrp_production.py` — nuevo motor genérico `_apunts_prorated_cost_raw`; `_apunts_prorated_emp_cost` refactorizado con parámetro `use_center`; `_apunts_labor_and_operation_real` y `_apunts_wo_cost` prorratan también el coste de centro (`wc.costs_hour`)
- `apunts_jr_wip_costes_of/models/mrp_production.py` — `_apunts_workorder_totals_real` prorrata máquina y amortización
- `apunts_costes_of/models/mrp_workcenter_productivity.py` — hook write/create para regenerar líneas de OFs afectadas al modificar un fichaje
- `apunts_costes_of/__init__.py` — importa `mrp_workcenter_productivity`

**Qué hace:**  
Cuando un operario ficha simultáneamente en varias OFs, el tiempo (y su coste) se distribuye proporcionalmente entre ellas. Si ficha de 10h a 14h en OF-1 y de 12h a 14h en OF-2:
- OF-1: 2h exclusivas (10-12) + 2h compartidas ÷2 (12-14) = **3h efectivas → 30 €**
- OF-2: 2h compartidas ÷2 (12-14) = **1h efectiva → 10 €**

El prorrateo aplica tanto al coste del empleado (`hourly_cost`) como al coste del centro de trabajo (`costs_hour`). En el módulo WIP también se prorrata la amortización (`apunts_amort_hour`). Los registros sin `employee_id` siguen usando duración bruta.

Al modificar un fichaje, el hook `write/create` en `mrp.workcenter.productivity` regenera automáticamente las líneas almacenadas de las OFs afectadas por el solapamiento.

**Para aplicar cambios:**
```
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal -u apunts_costes_of,apunts_jr_wip_costes_of --stop-after-init
docker compose start odoo
```

---

## [022] Corrección backorder en OFs divididas — `apunts_jr_wip_costes_of`

**Fecha:** 2026-06-05  
**Módulos:** `apunts_jr_wip_costes_of` (1.1.21)  
**Ficheros modificados:**
- `apunts_jr_wip_costes_of/models/mrp_production.py` — override `_cal_price` para capturar `ValueError: Expected singleton`

**Qué hace:**  
Al crear un albarán parcial desde una OF dividida, Odoo llamaba a `mrp_account._cal_price` que internamente hace `ensure_one()` sobre un conjunto de varios `stock.move`. Esto lanzaba `ValueError: Expected singleton: stock.move(...)` y bloqueaba la entrega.

El override captura ese error específico, lo registra en el log como warning y permite que el backorder continúe. El recálculo de precio estándar se omite solo para OFs divididas con múltiples movimientos de salida.

**Para aplicar cambios:**
```
docker compose run --rm odoo odoo -d javierramoslocal -u apunts_jr_wip_costes_of --stop-after-init
docker compose restart odoo
```

---

## [023] Bloquear FIN JORNADA con fichajes abiertos — `apunts_taller_control`

**Fecha:** 2026-06-05  
**Módulos:** `apunts_taller_control`  
**Ficheros modificados:**
- `apunts_taller_control/wizards/fin_jornada_wizard.py` — `action_confirmar_fin_jornada()` verifica fichajes abiertos antes de cerrar jornada
- `apunts_taller_control/wizards/fin_jornada_wizard_view.xml` — texto del aviso actualizado
- `apunts_taller_control/security/ir.model.access.csv` — restaurada regla de acceso para `apunts.fin.jornada.wizard.linea`

**Qué hace:**  
Antes, al pulsar "Confirmar y salir" en el wizard de fin de jornada, Odoo cerraba automáticamente los fichajes abiertos. Ahora, si el operario tiene alguna OF con fichaje activo (`date_end = False`), se muestra un `UserError` listando exactamente qué OFs están abiertas:

```
No puedes cerrar la jornada: tienes OFs con fichaje abierto:

  • WH/MO/00123 — Fase 1
  • WH/MO/00456 — Montaje

Desfíchate de cada una escaneando su código de barras y vuelve a intentarlo.
```

El operario debe deslogarse de cada OF manualmente (escaneando su código de barras) antes de poder cerrar jornada.

Nota: la clase `ApuntsFinJornadaWizardLinea` se mantiene vacía para evitar errores de registros huérfanos en BD (`ir.model` persiste aunque se elimine la clase Python).

**Para aplicar cambios:**
```
docker compose run --rm odoo odoo -d javierramoslocal -u apunts_taller_control --stop-after-init
docker compose restart odoo
```

---

## [024] Ventana desbloquear operario con dos casos — `apunts_taller_control` + `apunts_jr_gestion_taller`

**Fecha:** 2026-06-05  
**Módulos:** `apunts_taller_control`, `apunts_jr_gestion_taller`  
**Ficheros modificados:**
- `apunts_taller_control/models/hr_employee.py` — `action_apunts_desbloquear_taller()` abre el wizard en lugar de desbloquear directamente
- `apunts_jr_gestion_taller/wizards/corregir_fichaje_wizard.py` — reescrito completo con lógica de dos casos
- `apunts_jr_gestion_taller/wizards/corregir_fichaje_wizard_view.xml` — vista con secciones condicionales por caso

**Qué hace:**  
Al pulsar "Desbloquear operario" desde la ficha del empleado, en lugar de desbloquear directamente se abre un wizard que detecta automáticamente el motivo del bloqueo y muestra los campos relevantes:

**Caso 1 — Fichaje demasiado largo** (`tiene_fichaje_abierto = True`):
- Muestra aviso naranja "Fichaje abierto detectado"
- Pre-carga la OF del fichaje abierto (editable, con buscador)
- Al seleccionar la OT muestra "Fichado desde" (readonly, calculado)
- Campo para corregir la hora de salida
- Al aplicar: cierra el fichaje con la hora corregida y desbloquea al empleado

**Caso 2 — Inactividad sin fichaje activo** (`tiene_fichaje_abierto = False`):
- Muestra aviso azul "Operario sin fichaje activo"
- Buscador de OF (filtrado por OFs del operario, con opción "Buscar en TODAS las OFs")
- Dentro de la OF, buscador de OT
- Campos de rango horario (inicio y fin del periodo)
- Al aplicar: crea un nuevo registro `mrp.workcenter.productivity` con el `loss_id` resuelto dinámicamente
- Pre-rellena automáticamente el inicio con el `date_end` del último fichaje cerrado

En ambos casos:
- Muestra los datos del bloqueo (motivo + fecha)
- Tabla editable con todos los fichajes del operario (últimos 100)
- Campo "Motivo de la corrección" para auditoría (queda en el chatter del empleado)
- Desbloquea siempre al aplicar (independientemente de si se corrigió algo)

Nota técnica: `mrp.workcenter.loss` no existe en esta instalación de Odoo 18. El `loss_id` (requerido en `mrp.workcenter.productivity`) se resuelve dinámicamente via `Productivity._fields.get('loss_id').comodel_name` con fallback a copiar el `loss_id` de un registro existente.

**Para aplicar cambios:**
```
docker compose run --rm odoo odoo -d javierramoslocal -u apunts_taller_control,apunts_jr_gestion_taller --stop-after-init
docker compose restart odoo
```

---

## [025] Reunión semanal de Dirección: 6 indicadores, 34 KPIs con histórico semanal — `apunts_jr_dashboard_direccion` + `lira_dashboard_contabilidad`

Implementa el informe de programación del cliente (`Informe_Programacion_Dashboard_JR_Joan_Apunts.xlsx`, 9-sep-2026): el Panel de Dirección pasa de "foto de hoy + detalle" a **Panel (6 bloques) → KPIs del bloque → evolución semanal → detalle de siempre**.

**Modelos nuevos** (`apunts_jr_dashboard_direccion` 18.0.3.0.0):
- `apunts.kpi.bloque` / `apunts.kpi`: catálogo de los 6 Indicadores de Dirección y sus 34 KPIs (se siembra solo: `_sembrar()`), con la cabecera estándar calculada al vuelo: valor actual · objetivo · semana anterior · variación · misma semana año anterior · estado.
- `apunts.kpi.semana`: un valor por KPI y semana ISO. La semana **se cierra el lunes de madrugada y queda bloqueada** (el dato de la reunión no cambia aunque la contabilidad se corrija). La semana en curso se refresca a diario como "actual".
- `apunts.kpi.serie`: series precalculadas para la gráfica (valor, media móvil 4 semanas, límites verde/amarillo, misma semana año anterior, acumulado del año y objetivo acumulado). Se regeneran solas, también al cambiar un criterio.
- `apunts.kpi.motor` (abstracto): calcula los 34 KPIs para cualquier semana y reconstruye el histórico del año al instalar (`reconstruir_historico`). Reglas temporales del informe: € flujo = la semana; € saldo = foto al cierre; % económicos = acumulado del año; % operativos = solo esa semana.
- `apunts.dat.pago` + proyección: DAT (días de autonomía de tesorería) = tesorería + vencimientos de cobro − vencimientos de pago − pagos recurrentes configurables (nómina/SS e IVA sembrados con estimación de la contabilidad).

**Fórmulas** (las del informe, con las adaptaciones acordadas): eficiencia productiva solo sobre OT "comparables" (con tiempo previsto, con horas y cerradas ≤7 días tras su último fichaje); PMC/PMP con saldo medio y semáforo del PMP relativo al PMC; MACPRE = horas en OF (sin doble conteo) ÷ presencia de planta, fiable desde S26; MACOP = el de Geinprod (h. máquina ÷ h. operario, objetivo 1,25); entregas en fecha solo con fecha comprometida; CDC en días; TCP confirmación→entrega; retrabajo sobre las fases de retrabajo del supervisor.

**lira_dashboard_contabilidad** 18.0.3.7.0: `lira.ratio.criterio.relativo_a` + `evaluar()` (semáforo común); EBITDA unificado con la cascada (todos los gastos de explotación, no solo 60-65); ingresos financieros (76) en el resultado del P&G.

**apunts_barcode_workorder** 18.0.1.13.0: al autocerrar una fase por validación, `date_finished` = último fichaje real (no la hora de la validación), para que los informes semanales la cuenten en su semana.

Crons: `apunts_cron_kpi_actual` (diario 06:10) y `apunts_cron_kpi_cierre` (lunes 00:40). Migración 18.0.3.0.0 siembra todo y reconstruye el histórico. Umbrales del informe cargados en Criterios de ratios sin pisar los editados por el cliente.

Avisos: "misma semana año anterior" sale vacío hasta 2027 (contabilidad desde 31/12/2025); la semana en que se actualice, los cierres administrativos de fases atascadas ensucian la eficiencia una sola vez.

**Para aplicar cambios:**
```
docker exec odoo_javierramos_local-odoo-1 odoo -c /etc/odoo/odoo.conf -d javierramos_prod -u lira_dashboard_contabilidad,apunts_jr_dashboard_direccion,apunts_barcode_workorder --stop-after-init --http-port=8899
```

---

## [026] Estudio de usabilidad de Dirección: menú reagrupado, directorio por indicadores, nombres coherentes — `apunts_jr_dashboard_direccion` 18.0.3.1.0 + `lira_dashboard_contabilidad` 18.0.3.8.0

Aplicado tras revisar todo lo que ve dirección (28 pantallas en Dirección + 31 en Análisis de situación):
- **Menú Dirección** en 5 entradas de uso + Configuración: Reunión semanal · Panel Dirección · Histórico de KPIs · Facturación por mes · Cuadros de siempre (CMI · CMP) · Configuración (solo `account.group_account_manager`). «Evolución semanal» pasa a Configuración como «Fotos diarias de los KPIs (motor de las fotos)»; «Objetivos del cuadro de mando» también, con coletilla «(panel antiguo)».
- **Pestaña «Otros paneles»** reconstruida: 59 accesos en 11 bloques ordenados como la reunión (Reunión semanal → 6 indicadores → Cuadros de siempre → Taller → Manuales → Configuración), todos verificados.
- **«Margen bruto» → «Margen de contribución»** en el panel (2 pestañas), fotos diarias, objetivos y filtros (el campo técnico no cambia).
- **lira**: P&G renombrado «por periodos (por bloques)»; menú «Cuentas marcadas como Variables» retirado (modelo y vista siguen); orden de Contabilidad / Tesorería: P&G → Evolución de costes → Cobros y pagos → antigüedades → previsiones → ⚙.
- Drill-down del KPI «Horas de retrabajo» apuntaba a un xmlid inexistente → `lira_mfg_supervisor.action_lira_refabricacion`.

Pendiente de decisión (documentado en el estudio): retirar la pestaña «Cuadro de mando» del panel (duplica «Vista de siempre»), unificar los dos sistemas de objetivos (cartera 300.000 vs 400.000), guías de formación por indicador.

---

## [027] Gráficas por semanas en Análisis de Ventas y en Pedidos Pendientes de Entrega — `lira_dashboard_contabilidad` 18.0.3.9.0

- **Análisis de Ventas y Facturación**: al calcular el ranking se guarda también la serie semanal (`lira.ventas.semana`: el total de cada semana —facturado o pedido según la fuente— con importe, unidades y documentos). Se llega a la gráfica desde el resumen (botón «Ver gráfica») y desde la cabecera del ranking (botón «Gráfica por semanas», `display="always"`). Vistas: barras por semana, tabla dinámica por semana y lista. El total de la serie cuadra con el del ranking.
- **Pedidos Pendientes de Entrega**: la acción «Ver tabla» abre ahora `list,graph,pivot` sobre las mismas líneas: gráfica de valor pendiente por semana de entrega comprometida y pivote cliente × semana. Agrupadores nuevos en el buscador (semana/mes de entrega, semana del pedido) y filtros «Con fecha de entrega comprometida» / «Fecha de entrega ya pasada».
- Refactor interno de `lira.sales.analysis`: `_movimientos()`, `_clave_grupo()` y `_agrupar()` extraídos de `_collect()` para reutilizar los movimientos en la serie semanal.

---

## [028] Una sola cifra de facturación en todas las pantallas — `lira_dashboard_contabilidad` 18.0.3.10.0 + `apunts_jr_dashboard_direccion` 18.0.3.2.0

El cliente detectó que «Facturación» no cuadraba entre pantallas (Análisis de ventas 795.269 · P&G y Tablero 885.011 · Panel 884.277). Tres causas:
1. El Análisis de ventas, al agrupar por producto, **tiraba las líneas de factura sin producto** (31 líneas de texto libre, 89.008 €). Ahora van al grupo «Sin producto (líneas de texto libre)».
2. El Análisis, el Panel, Facturación por mes, el CMI y el motor de KPIs usaban la **base imponible del documento** (`amount_untaxed_signed`); el P&G y el Tablero, las **cuentas 70x**. Diferían en 734,25 € por una «Retención del 5 % sobre certificación de obra» (JR/2026/00038) contabilizada en la 431: correcta contablemente, no es ingreso. **Definición única desde ahora: facturación = ingresos por ventas contabilizados (70x) por fecha contable**, en las 10 pantallas.
3. Al pasar a 70x, la **semana ISO 1 (29-12 → 4-1) arrastraba los asientos de apertura del 31/12** (1,87 M€ de ventas de 2025). Los flujos semanales (facturación, pedidos, compras) se acotan ahora al año natural de la semana (`ini_flujo`/`fin_flujo` en `kpi_motor`, `ini_f`/`fin_f` en `cmi_semana`).

Verificado 01/01→10/09/2026 = 885.011,49 € en: Análisis por producto (cabecera y ranking), Análisis por cliente, gráfica semanal de ventas, P&G, Tablero, Panel Dirección, Facturación por mes, CMI registro semanal (suma) y Reunión semanal (suma fact_semana). Migración 18.0.3.2.0 rehace fact_semana/pedidos_semana/cdc y el CMI.

---

## [029] Tablero de Contabilidad: balance de situación en columna — `lira_dashboard_contabilidad` 18.0.3.11.0

Estético, a petición de dirección: el bloque «Balance de situación» deja de ir a la derecha de la cuenta de resultados y pasa a ir **debajo de «Distribución de costes (% s/ingresos)» y encima de «Ciclo de maduración»**, todo en una sola columna (`ld_one_col` en `dashboard.css`; el XML solo cambia la clase del contenedor).

Además, la cuenta de resultados del Tablero deja de excluir la variación de existencias (710000001) y las subvenciones (740000001) de los ingresos de explotación: así su EBITDA y su beneficio neto coinciden con el P&G por periodos (antes diferían en 1.292,18 €).

---

## [030] «En curso (real)» pasa a llamarse «Coste real» — `apunts_jr_wip_costes_of` + `apunts_jr_parciales_of`

Solo etiquetas, a petición de dirección: la tarjeta del Resumen de fabricación en curso (WIP), la pantalla de costes de la OF, el PDF de coste de la OF y la cadena de costes de OFs parciales. El campo y el cálculo no cambian (material recibido + mano de obra fichada + máquina invertida).

---

## [031] Resumen Carga Centros: solo lo esencial en curso; OT cerradas al histórico — `apunts_jr_carga_centros` 18.0.1.6.0

- Vista **En curso**: quedan las 4 tarjetas (centros activos, con trabajo pendiente, horas pendientes, días pendientes) y el bloque de órdenes de trabajo con **abiertas** y **en espera**. Fuera las tarjetas de horas/días reales a 7/15/30 días y el histórico total (redundantes, según dirección).
- Vista **Histórico**: la tarjeta de **OT cerradas** pasa aquí y respeta el periodo (`hist_ot_cerradas_n`, cerradas por fecha de cierre dentro del rango); el botón «Ver órdenes cerradas» filtra por el mismo periodo.
- Los campos de 7/15/30 días siguen en el modelo (los usa la lista de centros y las fotos diarias); solo desaparecen de esta pantalla.

---

## [032] Jornada esperada real: «Operario de planta» en la ficha del empleado — `apunts_jr_gestion_taller` 18.0.1.18.0 + `apunts_jr_dashboard_direccion` 18.0.3.3.0

- Nuevo campo `hr.employee.apunts_planta` («Operario de planta», pestaña Taller (Apunts) de la ficha; columna y filtro en Operarios (resumen horas)). La migración lo marca de inicio a quien ha fichado en órdenes en los últimos 90 días, salvo los excluidos del rendimiento.
- **KPIs de fichaje**: la jornada esperada ya no es «días L-V × 8 h × todos los empleados» sino la suma, para toda la plantilla (planta y oficina fichan presencia), de las horas de **su calendario laboral** en el periodo, festivos descontados (`_apunts_horas_esperadas`, cálculo día a día: el helper estándar de Odoo devuelve horas en fin de semana cuando el rango empieza en sábado). Fuera solo las fichas marcadas «No contar en rendimiento» (empresa, gestión, pruebas). La tabla lista a todos (aunque no hayan fichado).
- **MACPRE** (Reunión semanal): el denominador de presencia y el numerador de horas en OF usan el mismo criterio de planta; su histórico se rehace.

---

## [033] Entregas del año: gráfica del desvío en días — `apunts_jr_dashboard_direccion` 18.0.3.4.0

- `stock.picking`: campos almacenados `apunts_dias_desvio` (entrega real − comprometida, en días; + tarde / − antes) y `apunts_dias_retraso` (solo lo tarde), con agregador media.
- «Entregas del año (en fecha / tarde)» abre ahora con lista propia (comprometida, entregado, desvío, en fecha, colores por gravedad), **gráfica de barras por semana con el desvío medio** y pivote cliente × semana; abre ya agrupada por semana de entrega (agrupadores nuevos por semana/mes).
- La fecha límite pasa a ser **solo la fecha comprometida** del pedido (antes, si no había, se usaba la fecha del pedido): un pedido sin compromiso no se puede medir y queda fuera, igual que en la Reunión semanal.

---

## [034] P&G con porcentajes y adiós al «margen de contribución» — `lira_dashboard_contabilidad` 18.0.3.12.0 · `apunts_jr_dashboard_direccion` 18.0.3.5.0

- **P&G por Periodos**: variables directos, semivariables, fijos operativos, estructura y EBITDA llevan entre paréntesis su % sobre la facturación (el resultado ya lo tenía). Facturación sin %.
- **Margen de contribución retirado de todas las pantallas** (réplica de la empresa: es un término de empresa comercial, a un fabricante no le aporta y crea dudas): tile del P&G, ratio y tarjeta del Tablero de Contabilidad, tarjeta 7 del Panel Dirección, KPI de la Reunión semanal (con su histórico y semáforo), foto diaria y objetivo.
- La tarjeta 7 del Panel Dirección pasa a ser **EBITDA del año** (€ y % sobre facturación, misma cascada que el P&G) y abre el P&G. La foto diaria y los objetivos admiten EBITDA en su lugar.
- Migración automática: borra el KPI, sus series, fotos, objetivo y criterio de semáforo antiguos. También se retira la alerta «Margen bruto bajo» del Tablero.

---

## [035] Fuera el EBIT — `lira_dashboard_contabilidad` 18.0.3.13.0

- **P&G por Periodos**: se retira el tile «EBIT» de la fila de partidas después del EBITDA (petición de la empresa). El cálculo interno (EBITDA − amortizaciones) se mantiene porque de él sale el resultado.
- **Tablero de Contabilidad**: la línea calculada de la cuenta de resultados pasa de «EBIT (Res. explotación)» a «Resultado de explotación», para que el término no aparezca en ninguna pantalla.

---

## [036] P&G por Periodos: % a cero y Resultado descolgado — `lira_dashboard_contabilidad` 18.0.3.14.0

- **% a 0,00**: los registros de P&G abiertos antes de la actualización [034] no tenían calculados los nuevos % por bloque (columnas nuevas, vacías) y, al volver a esa pantalla desde el historial del navegador, salían a cero. La migración recalcula todos los registros existentes; los que se abren desde el menú siempre se calculan al abrir.
- **Resultado en la misma fila**: la cascada (facturación → resultado) pasa a una fila propia a todo el ancho, con el % de cada bloque en una línea pequeña bajo la cifra, así las 8 cifras caben al mismo nivel. En pantallas estrechas vuelve a saltar de línea.

---

## [037] Ratios «sobre facturación», no «sobre ventas» — `apunts_jr_dashboard_direccion` 18.0.3.6.0 · `lira_dashboard_contabilidad` 18.0.3.15.0

Solo nomenclatura, a petición de dirección: los ratios del P&G ya dividían por la facturación contabilizada (70x), no por pedidos. Renombrados los 8 KPIs (EBITDA, COV, EDV, variables, semivariables, fijos, amortizaciones, gastos financieros), los 7 criterios de semáforo y la pregunta del bloque 3 («¿Dónde se consumen los 100 € facturados?»). En lira, los textos de ayuda de COV, EDV y Margen neto. La migración resiembra el catálogo para renombrar lo que ya existe en BD.

---

## [038] Stock por cliente (valorado) — `lira_dashboard_contabilidad` 18.0.4.0.0

- **Campo «Cliente» en la ficha del producto**, rellenado solo con el prefijo de 4 dígitos de la referencia interna (0612 = Stadler, 2175 = Hidragrup…) y, si no lo tiene, con el cliente que más veces la ha comprado (pedidos + facturas). Editable: lo que se toca a mano deja de ser automático y ya no se pisa. Un cron diario lo pone a las referencias nuevas y hay botón «Recalcular clientes».
- **Nueva pantalla «Stock por cliente»**, en Inventario → Informes y en Contabilidad → Análisis de situación → Existencias. Lista, tabla dinámica y gráfica, agrupada por cliente de entrada, con unidades, valor a coste y valor a precio de venta. Lo no atribuible (materia prima, consumibles) queda en el grupo «Ninguno».
- **Pedidos Pendientes de Entrega**: columnas de stock y valor del stock por línea (ajustadas en [039] y [040]).
- Migración automática: asigna el cliente a todo el catálogo existente.
- Aviso detectado con la pantalla: el producto «PORTES A FRANCIA POR GRUPAJE» tiene 1,5 uds en stock y un precio de venta de 253.495 € en su ficha; descuadra el total a venta hasta que lo corrijan.

---

## [039] Pendientes de entrega: stock disponible, previsto y valor sin contar dos veces — `lira_dashboard_contabilidad` 18.0.4.2.0

- Columnas alineadas con la ficha del producto: **Stock disponible** (a mano) y **Stock previsto** (a mano + entradas − salidas), que antes se llamaba «Stock disp.» y confundía.
- Si una referencia está en varios pedidos pendientes, el stock disponible y su **Valor stock** se ponen en el pedido más antiguo y a cero en los demás (criterio de Joan): al agrupar por cliente ya no se multiplican. Detectado con el centrador 0612027318: 138,60 € reales salían como 277,20 €.
- El previsto se repite en cada línea porque es informativo y no se suma en el pie.

---

## [040] Pendientes de entrega: tablas viejas regeneradas y orden de columnas — `lira_dashboard_contabilidad` 18.0.4.3.0

- La tabla de detalle se guarda por usuario al pulsar «Ver tabla»; tras el cambio de cálculo [038], quien volvía a ella por el historial veía los números antiguos (disponible a 0 y valor = previsto × precio). La migración regenera la tabla de todos los usuarios con el cálculo nuevo.
- Columnas en este orden: Stock previsto · Stock disponible · Valor stock (€).

---

## [041] Reunión semanal: navegar por semanas — `apunts_jr_dashboard_direccion` 18.0.3.14.0

- **Rango de varias semanas → resumen del periodo (acumulado)** (18.0.3.14.0): las tarjetas de siempre con el dato del periodo entero. Flujos (facturación, pedidos) sumados; ratios semanales (eficiencia, MACPRE, MACOP, TCP, retrabajo, entregas, desviación) en media de las semanas con dato; acumulados del año y fotos (EBITDA, COV, CDC, DAT, cartera…) a cierre del periodo. La comparación es con el **periodo anterior de la misma duración**. Botón «Ver por semanas» en la cabecera para abrir el mismo periodo en una columna por semana.

- **Rango de varias semanas → tarjetas en columnas** (18.0.3.13.0): en vez de mandar a la tabla dinámica, se abren las mismas tarjetas con una columna por semana; de entrada solo el KPI principal de cada indicador (6 por semana) y, quitando el filtro «Solo el KPI principal», los 33. Tabla dinámica y lista siguen al lado.

- En la cabecera de la **Reunión semanal** hay tres botones: **◀ Semana anterior**, **Elegir fechas…** y **Semana siguiente ▶**. El título indica la semana que se está viendo; al llegar a la última se vuelve al panel normal.
- «Elegir fechas…» (también en el menú Dirección → Consultar otra semana): se eligen dos fechas y, si caen en una sola semana, se abre el mismo panel de la reunión (indicadores → KPIs) con los valores **tal y como quedaron guardados esa semana**: cobertura de cartera, EDV, eficiencia, semáforos… Al entrar en un indicador se mantiene la semana elegida.
- Si el rango abarca varias semanas, se abre la tabla de KPIs por semanas (agrupada por indicador) para compararlas.
- Por defecto propone la última semana cerrada. Las semanas cerradas son inmutables, así que lo que se consulta es exactamente el dato de aquella reunión.

---

## [042] Histórico semanal comparable: cartera y cobertura reconstruidas — `apunts_jr_dashboard_direccion` 18.0.3.12.0

- Al navegar por semanas pasadas, «Actividad comercial» salía vacío en muchas semanas: la cartera pendiente y la cobertura (CDC) dependían de la foto diaria del panel, que no existía en esas semanas. Ahora **se reconstruyen a cierre de cada semana** con los pedidos confirmados y los albaranes entregados hasta ese domingo, igual para todas las semanas.
- El **WIP** de una semana sin actividad de taller (vacaciones) hereda la última foto: el dato no pudo cambiar. Con actividad y sin foto no se inventa nada.
- Los KPIs de producción y servicio de una semana sin OTs ni albaranes ni fichajes (agosto) siguen sin valor, porque no hubo actividad: la tarjeta lo dice así («sin actividad esa semana») y el semáforo pone «Sin dato» en vez de «Sin objetivo».
- Migración automática: rehace esas filas y rellena los huecos de todas las semanas cerradas sin tocar las cerradas en vivo.

---

## [043] PDF de la orden de producción: la cantidad ya no se lee pegada al producto — `apunts_barcode_workorder`

- En la OF impresa, «Producto» y «Cantidad a producir» iban en columnas contiguas y un nombre largo («03640001-RIEL 1 METRO ALUMINIO») partía en «RIEL 1» justo al lado del «455,0000», leyéndose 1455. Ahora el producto ocupa más ancho con aire a la derecha y la cantidad va separada por una línea vertical, en grande y en negrita.

---

## [044] URGENTE · Fin de jornada roto en producción: método de horas esperadas pisado — `apunts_jr_gestion_taller` 18.0.1.19.0

- **Síntoma** (15-sep, producción): al confirmar el fin de jornada, error «_apunts_horas_esperadas() missing 1 required positional argument: 'fin'». También fallaba en silencio el bloqueo diario de jornada y el desbloqueo/corrección de fichajes, que usan el mismo método.
- **Causa**: en [032] el cálculo de jornada esperada por rango (calendario de cada empleado, festivos descontados) se añadió a `hr.employee` con el mismo nombre que el método de un solo día de `apunts_taller_control`, y lo pisó.
- **Arreglo**: el cálculo por rango pasa a llamarse `_apunts_horas_esperadas_rango`; el método de un día vuelve a ser el original. Solo lo usaba la pantalla de KPIs de fichaje, que se ha adaptado. No cambia ningún número.

---

## [045] Stock por cliente: los unitarios ya no se suman al agrupar — `lira_dashboard_contabilidad` 18.0.4.4.0

- Al agrupar por cliente, «Coste unit.» y «Precio venta unit.» mostraban la suma de los unitarios de todas las referencias del grupo (p. ej. 17.102 € en «Ninguno»), un número sin sentido que se confundía con el valor. Ahora esas dos columnas no se agregan; las que suman siguen siendo Cantidad, Valor a coste y Valor a venta.
- Comprobado en producción: Valor a coste (67.334,31 €) coincide con Inventario → Informes → Valoración; el «medio millón» anterior era el producto «PORTES A FRANCIA POR GRUPAJE» con precio de venta 253.495 € (corregido a 1 € el 17-sep a las 09:55), que inflaba la columna a venta.

---

## [046] Dos informes de stock: piezas por cliente y materia prima — `lira_dashboard_contabilidad` 18.0.4.14.0

- **Tipo de stock** en la ficha del producto, calculado por el código (referencia interna o principio del nombre): solo dígitos → **pieza de cliente**; dígitos + letras (L, X, A, PI, CI, AN, S, M, PA, TE…) → **material y servicios para piezas de cliente**; sin código de cliente → **materia prima y compras**; categorías de consumibles/EPIs/ferretería/mercaderías/portes → **consumibles y otros**.
- **Stock por cliente** abre ya solo con piezas de cliente (filtro quitable); columnas opcionales Tipo y Con venta; filtro «Sin venta confirmada (solo presupuesto o nada)» para localizar lo que el cliente llama «presupuestado».
- **Stock por cliente se valora a precio de venta** (unidades, PVP y valor a venta); el valor a coste queda como columna opcional oculta. El coste de las piezas fabricadas no se calcula de ninguna forma: es el de la ficha, que hoy está a cero.
- **Nuevo informe «Stock materia prima»** (Inventario → Informes y Análisis de situación → Existencias): materia prima y material de cliente agrupados por categoría, a coste; filtro para añadir consumibles.
- **Precio de venta**: si la ficha no tiene PVP, el automatismo (cron/Recalcular clientes/migración) le pone el último precio de venta confirmado y marca «Con venta confirmada». En la copia del cliente: 37 referencias con stock sin PVP → 7 (las 7 nunca se han vendido).
- La categoría de consumibles manda sobre el código (un disco o un guante con referencia numérica se saca de «piezas» cambiándolo de categoría). El cliente por prefijo se lee también del nombre cuando la referencia interna está vacía (piezas antiguas).
- Migración: recalcula el tipo de todo el catálogo y de los quants y vuelve a asignar clientes. (La 18.0.4.13.0 solo limpia columnas de una prueba descartada en local.)

---

## [047] PDF «Coste de OF»: fuera el cuarto de página en blanco y la segunda hoja vacía — `apunts_jr_wip_costes_of` 18.0.1.16.0

- El informe pinta su propia cabecera y su pie dentro de la página, pero estaba ligado al formato A4 de la empresa, que reserva 65 mm arriba para la cabecera estándar. Resultado: un cuarto de hoja en blanco encima del logo y el pie cayendo a una segunda página vacía.
- Formato de papel propio «Coste de OF (A4 sin cabecera estándar)» con márgenes de 10/10/8/8 mm y sin hueco de cabecera. Mismo contenido, en una sola hoja.

---

## [048] Etiquetas de albarán: los códigos de barras no se leían — `javier_ramos_taller_simple` 18.0.1.1.0

- En las etiquetas de recepción y de entrega, los códigos de barras (ORDEN y ARTÍCULO) se generaban a 200×60 px y se estiraban a 17 mm de alto: al imprimir se fundían barras (medido en la etiqueta del cliente: 38 barras donde Code128 necesita 46) y el lector de la tablet no leía la OF.
- Ahora se generan a 600×100 px, la resolución que usa Odoo en sus propias etiquetas. Mismo tamaño en papel, barras nítidas. Sin cambios de datos.
- El código de barras de ARTÍCULO salía vacío en casi todo el material comprado (482 de 487 líneas de compra desde junio no tienen referencia interna; el código va en el nombre). Ahora, sin referencia ni código de barras, se usa el código del principio del nombre («05840055X-ACERO…» → 05840055X).
- El módulo no tenía versión en el manifiesto (contaba como 18.0.1.0); se le pone 18.0.1.1.0.

---

## [049] MACPRE con toda la plantilla, MACOP solo con planta — `apunts_jr_dashboard_direccion` 18.0.3.15.0 · `apunts_jr_gestion_taller` 18.0.1.20.0

- Se había interpretado al revés: el marcador «Operario de planta» de la ficha del empleado limitaba el MACPRE. Criterio correcto (Joan, 21/09/2026): **MACPRE** = horas en OF ÷ presencia fichada de **toda la plantilla**, oficina incluida; **MACOP** = horas máquina ÷ horas en OF de **solo los operarios de planta**. Así se ve si las horas de planta cubren la presencia global.
- Migración: borra el histórico semanal de MACPRE y MACOP y lo rehace entero con el criterio nuevo. Textos de ayuda del catálogo y de la ficha del empleado actualizados.

---

## [050] Tablero de Contabilidad: préstamos, amortizaciones y existencias — `lira_dashboard_contabilidad` 18.0.4.15.0

- Petición de Vicky (correo de Franklin del 21/09/2026): ver en las tarjetas de los diarios PRESTAMOS, AMORT y EXIST del tablero de Odoo el nivel de endeudamiento, el tiempo que queda del préstamo y más datos. Ángel descartó tocar las tarjetas de diario (no escala). Alternativa: **sección nueva en el Tablero de Contabilidad** (Análisis de situación), donde ya viven los demás indicadores; cada dato nuevo es un campo más.
- **Préstamos en curso** (de Contabilidad → Préstamos): deuda viva, nivel de endeudamiento bancario (deuda viva ÷ patrimonio neto), cuota del próximo mes, cuotas que quedan, último vencimiento y tabla por préstamo. Botón «Ver préstamos».
- **Activos y amortizaciones** (de Contabilidad → Activos): valor neto, valor de adquisición, ya amortizado y %, amortización del próximo mes y de los próximos 12 meses, última amortización prevista. Botón «Ver activos».
- **Existencias**: saldo contable del grupo 3 a la fecha y fecha del último ajuste del diario EXIST, frente a lo que hay en la nave según Odoo (materia prima a coste, piezas de cliente a venta). Botones a Stock materia prima y a los asientos.

---

## [051] Cumplimiento de proveedores — `apunts_jr_dashboard_direccion` 18.0.3.16.0

- Petición de Xavi y Cinthia (audios 22/09/2026): entender «fecha programada» y «fecha efectiva» de las recepciones y poder controlar a los proveedores. En cada recepción validada (no devolución) quedan guardadas la **programada** (fecha límite del pedido de compra, o la programada del albarán), la **efectiva** (validación) y el **retraso en días**.
- Informe **«Cumplimiento de proveedores»** en Compra → Informes y en Inventario → Informes: lista agrupada por proveedor con retraso medio y % en fecha, pivote y gráfica; filtros «Llegaron tarde», «Este año», «Últimos 90 días».

## [052] Devoluciones a proveedor: origen obligatorio — `javier_ramos_taller_simple` 18.0.1.2.0

- Campo **«Origen de la devolución»** en el albarán (error de compras / fallo del proveedor / mercancía en mal estado). Aparece solo en las devoluciones de recepciones con destino proveedor y es obligatorio para validarlas. Columna opcional en la lista, filtro «Devoluciones a proveedor» y agrupación por origen.

## [053] Etiqueta de expedición: fecha y orden de fabricación — `javier_ramos_taller_simple` 18.0.1.2.0

- Fila nueva **«Fecha expedición»**: la de validación de la salida; si se imprime antes de validar, la prevista.
- El código de barras **ORDEN** pasa a ser la **orden de fabricación** de la pieza y no el pedido de venta (que sigue debajo en «Pedido JR»). Las líneas de salida casi nunca llevan la OF puesta (3 % desde junio), así que se busca: la OF enlazada al pedido de venta y, si no hay, la última OF del producto (con parciales, el último tramo). Una etiqueta por línea, como hasta ahora.

---

## [054] PDF de la OF: duraciones también en OT sin escandallo — `javier_ramos_taller_simple` 18.0.1.3.0

- Audio de Xavi (21/09, OF 01215 y 01218): «Duración» y «Duración unitaria» salían vacías. El PDF solo las calculaba desde la operación del escandallo, y esas OF no tienen escandallo (fases creadas a mano). Ahora, sin operación, usa el tiempo previsto de la propia OT (total y dividido por la cantidad).
- Lo que no se toca: las cantidades de los componentes salen del propio OF (en 01215/01218 están a 0 en la OF); y la «fecha límite» sale si la OF la tiene (hoy las dos la tienen: 25/11/2026).

## [055] Tablet: los PDF del producto no se abrían — `apunts_barcode_workorder` 18.0.1.15.0

- «En eixa orden els PDF no van» (FAB/MO/01334, FRAME): los tres PDF de taller del producto se subieron con el widget y quedaron **huérfanos** (`res_id = 0`); Odoo solo deja abrir un adjunto huérfano a quien lo subió, así que el operario los veía en la lista pero no se abrían. En producción hay 13 adjuntos así en 8 productos.
- Ahora, al guardar documentos de taller en un producto, se enlazan a él (`res_model/res_id`), y la migración arregla los existentes.

## [056] Tablet: mantener pulsado el nombre de la fase para leerlo entero — `apunts_barcode_workorder` 18.0.1.15.0

- Vídeo de Xavi (21/09): el nombre de la fase sale cortado con «…». Manteniendo pulsado el nombre medio segundo se despliega completo (varias líneas, fondo amarillo suave) y al soltar vuelve a plegarse. En escritorio también sale como tooltip.

---

## [057] Stock por cliente: métodos borrados por la marcha atrás de [047] — `lira_dashboard_contabilidad` 18.0.4.16.0

- Al deshacer el cálculo de coste desde la OF ([047]) se recortó de más `models/lira_stock_cliente.py` y desaparecieron `_lira_mapas_cliente` y `_lira_ultimo_precio_venta`, que usa `_lira_asignar_cliente` (cron nocturno, botón «Recalcular clientes» y migraciones 4.5.0 / 4.8.0).
- En local no saltó porque las dos BDs ya estaban en 4.15.0 (esas migraciones no volvían a ejecutarse) y los crons están neutralizados. En producción (BD en 4.3.0) la migración 4.5.0 sí se ejecutó y la actualización por API falló con `AttributeError: 'product.template' object has no attribute '_lira_mapas_cliente'`; Odoo hizo rollback y producción quedó intacta en las versiones antiguas.
- Se restauran los dos métodos tal cual estaban (mayoría de compras por prefijo de 4 dígitos y por variante; último precio de venta con descuento). Verificado en local: 42 prefijos, 529 variantes con comprador, 447 precios; `_lira_asignar_cliente()` corre sin error en ambas BDs.
- **Despliegue**: hay que volver a subir SOLO la carpeta `lira_dashboard_contabilidad` al servidor (los otros cinco módulos ya subidos están bien) y relanzar la actualización.

## [058] Resumen de inventario: la gráfica y «A recibir» abrían la lista de todos los albaranes sin filtros — `apunts_jr_dashboard_direccion` 18.0.3.17.0

- Vídeo de Xavi (23/09): en Inventario → Resumen, pinchar en las barras de Recepciones (retrasado / hoy / mañana) o en «A recibir» abría siempre la misma lista «Pendiente» con todos los albaranes (entradas, salidas, de cualquier fecha). Desde el día anterior.
- **Causa**: Odoo elige como vista por defecto de un modelo la vista primaria de menor `priority` y, a igualdad (16), la de nombre alfabéticamente menor. La vista de búsqueda del informe «Cumplimiento de proveedores» ([051], `stock.picking.apunts.proveedores.search`) pasó a ser el buscador por defecto de **todos** los albaranes: como no tiene el campo tipo de operación ni los filtros hoy/mañana/retrasado, las acciones del Resumen (que solo mandan `search_default_*` en el contexto) perdían todos sus filtros.
- **Arreglo**: `priority` 99 **solo en esa vista** (`apunts_view_picking_proveedores_search`); la acción del informe la referencia explícitamente, así que el informe no cambia. Verificado en local (Playwright: «A recibir» → 21 recepciones con facetas Recepciones · Listo; barra «Hoy» → 10 con Recepciones · Hoy) y en producción por API (buscador por defecto de albaranes = `stock.view_picking_internal_search`).
- **Producción**: corregido en caliente por API (escritura de `priority` en esa vista) el 23/09 a las 16:20, sin subir código. La 18.0.3.17.0 queda para la próxima subida (fija la misma prioridad que ya tiene la BD).
- Nota: durante el arreglo se probó poner prioridad 99 a las 45 vistas nuestras sobre modelos estándar; Joan lo descartó («habrá módulos que sí necesitan ser la vista por defecto») y se dejaron todas como estaban, en código y en producción. El rastreo sirve como diagnóstico: `env['ir.ui.view'].default_view(modelo, tipo)` → si devuelve una vista nuestra sin querer, es esto.


## [059] Histórico de fichajes: se pueden eliminar fichajes — `apunts_jr_gestion_taller` 18.0.1.21.0

- Audio de Xavi (23/09): quiere borrar los fichajes de prueba del operario ALEXAPUNTS (usuario de Apunts, archivado; 73 líneas, 173 h de las que 169 h son tres líneas sin OT de marzo) y no puede: desde la OT ya hecha Odoo no deja tocar los tiempos, y la lista Histórico de fichajes tenía `delete="0"`.
- La lista pasa a `delete="1"`: seleccionando filas, Acciones → Eliminar. Sin más reglas (no hay ninguna en código que impida borrar tiempos de OTs cerradas; el permiso lo da el grupo de fabricación). «Operarios fichados ahora» sigue sin poder borrar.
- Pendiente de subir a producción junto con el resto (dashboard_direccion 3.17.0).

## [060] Gestión Taller por compañía: la presencia ya no mezcla empleados de otras empresas — `apunts_jr_gestion_taller` 18.0.1.22.0

- Audio y capturas del 23/09 (Mª José): en **Histórico presencia** salía el operario «AUSINA» con 10 registros (9 ausencias + 1 presencia) que ella no ha fichado nunca, y al pulsar «Abrir» saltaba «Error de acceso… registros ultrasecretos» sobre `hr.leave`.
- **Causa**: hay 4 compañías (`JAVIER RAMOS, S.L`, `JAVIER RAMOS,S.L.` —duplicada—, `autis`, `Ramos Rental`). El empleado AUSINA (id 17, correo mjose@jramos.com, duplicado de Mª JOSÉ TARAZONA AUSINA) es de la compañía duplicada. `hr.employee`, `hr.attendance`, `hr.leave` y `mrp.workcenter.productivity` tienen regla multiempresa y filtran bien; **nuestros modelos propios no la tenían**: `apunts.historico.presencia` es una vista SQL sin `company_id`, así que enseñaba a todas las compañías, y al abrir una fila ajena la regla de `hr.leave` denegaba el acceso (el error era de regla, no de permisos).
- **Arreglo** (opción elegida por Joan: separar por compañía, no borrar el empleado):
  - `apunts.historico.presencia`: campo `company_id` (del empleado) en el modelo y en la vista SQL, columna opcional y agrupación por compañía.
  - `apunts.taller.desbloqueo`: `company_id` relacionado y guardado (migración 18.0.1.22.0 que lo rellena; 0 filas a cambiar, ninguna era de otra compañía).
  - Reglas multiempresa globales para los dos modelos en `security/ir_rule.xml`, iguales a las de Odoo.
  - **KPIs de fichaje**: los agregados van con `sudo()` (los lee el Panel Dirección), que se salta las reglas → ahora acotan a `self.env.companies` en empleados y fichajes.
- Verificado en local (`javierramos_prod`): presencia 780 → **770 filas con solo JAVIER RAMOS, S.L activa** (las 10 de AUSINA solo si se activa también la compañía duplicada); KPI 16 → 15 empleados; el grupo AUSINA desaparece de la lista.
- Pendiente de subir a producción junto con lo demás (dashboard_direccion 3.17.0, gestion_taller 1.22.0).

## [061] OF en curso: madres dentro, venta sin repetir en las hijas, cliente y fecha de entrega heredados — `apunts_jr_wip_costes_of` 18.0.1.17.0

- Vídeos y audios de Xavi (23/09), proyecto Iberian Automation (pedido S00662, 9.000 €, madre FAB/MO/01415 y 28 hijas):
  1. **Venta repetida en las hijas**: 8 hijas mostraban 9.000 € cada una. Cuando la OF encontraba el pedido por el grupo de aprovisionamiento y ninguna línea casaba con su producto, se quedaba con el **pedido entero**. Ahora, si la OF es hija, su venta es 0 (la lleva la madre); la OF principal de un pedido vendido por partes sigue valorando el pedido entero, como antes.
  2. **La madre no salía en curso**: el criterio era «dinero metido» (material consumido o compra recibida) y los componentes de una madre son OF hijas. Ahora una OF está en curso por sí misma **o si alguna de sus hijas lo está** (campo `apunts_wip_propio` con el criterio de siempre + `apunts_is_wip` recursivo que mira a las hijas).
  3. **Hijas sin cliente**: si la OF no encuentra pedido propio, coge el cliente de su madre (recursivo).
  4. **Fecha de entrega a la vista**: campo nuevo `apunts_fecha_entrega` = entrega del pedido (línea, pedido o campo de Studio `x_studio_venta`); si es hija, la de su madre; si no hay nada, la fecha límite de la OF. La fecha programada no se toca (la ajusta el taller). En la franja azul de la OF, junto a las fechas del formulario, como columna «Entrega» en OFs en curso y en la lista estándar de Órdenes de fabricación; filtros y agrupación por mes de entrega pasan a usarla.
- Enlace madre ↔ hijas guardado: `apunts_of_madre_id` (enlace manual o la OF cuyo nombre es el Origen) y su inversa `apunts_hija_ids`. Filtros nuevos «OF madre de proyecto» / «OF hija», agrupación por cliente y por OF madre, columna opcional «OF madre».
- Las dependencias con `x_studio_venta` se declaran solo si el campo existe en la BD (es de Studio): sin ello, cambiar la fecha de un pedido enlazado por ese campo no actualizaba la OF (lo destapó la prueba con la 01331).
- El disparador de compras y el botón «Forzar recálculo» del Resumen WIP recalculan también el criterio propio.
- Migración 18.0.1.17.0: recalcula en curso, venta y márgenes de las **OF abiertas** (el histórico de OF hechas no se reescribe) y cliente y fecha de entrega de todas las no canceladas.
- Verificado en local (`javierramos_prod` y `javierramos_0904`): la lógica nueva nunca quita ni cambia un cliente que la anterior diera (0 casos) y añade el de la madre a 42 / 65 OF; madre sin hijas con material → sale del WIP y vuelve al deshacerlo; la fecha de entrega sigue al pedido por línea y por Studio; una OF suelta enlazada a mano hereda cliente y entrega con venta 0; Playwright: franja «Entrega: 02/10/2026», «Fecha de entrega» y «OF madre» en el formulario, columna «Entrega» en las dos listas.
- **Efecto previsto en producción** (simulado por API en solo lectura el 24/09): OF en curso 101 → 105 (entran las madres 01331, 01383, 01415, 01326); venta en curso 255.253 € → 199.604 € (−72.000 € de las 8 hijas IAR, +16.351 € de las madres); en curso sin cliente 35 → 7.
- **Revisión de impacto en KPIs (25/09, a petición de Joan)**: los indicadores de dirección solo leen de fabricación el **coste real** de las OF en curso (`direccion_resumen.wip_valor` → KPI «Fabricación en curso» y su serie semanal; `cmi_semana.encurso` → «En curso», «En curso + stock», «Cantidad ejecutada»). Ninguno lee venta, cliente ni márgenes de la OF. Una madre que entra en curso solo por sus hijas no tiene, por definición, material consumido ni compra recibida, así que su coste real es 0 (hoy en producción las 4 madres: 0,00 €) → **el KPI no cambia** (51.215,45 € antes y después). Comprobado en local con el código nuevo: Panel «Fabricación en curso» 33.627,19 € = valor anterior; motor semanal, cron «actualizar semana actual» y cron CMI sin errores y con el mismo valor. El histórico semanal son fotos guardadas y no se recalcula. Pruebas de humo: alta de OF con hijas automáticas (enlace madre correcto), fichar/parar como usuario Planta en una hija, cerrar una hija (su coste pasa a la madre sin duplicarse). Único efecto visible fuera del WIP: el «Coste OF» de una hija suelta sale con venta 0 y margen negativo; el margen del proyecto se lee en la madre. Caso teórico futuro: una madre con compra de servicio externo o reposición aún sin recibir y hijas en curso sumaría esa compra al coste en curso (antes no hasta recibirla); hoy 0 casos.
- Pendiente de subir junto con lo acumulado (dashboard_direccion 3.17.0, gestion_taller 1.22.0).
