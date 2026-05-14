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
