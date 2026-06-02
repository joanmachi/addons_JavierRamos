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
