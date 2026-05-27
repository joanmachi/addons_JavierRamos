# `apunts_jr_wip_costes_of` — Documentación de cálculos

---

## 1. Coste de producto — `product.product`

### Campo `apunts_coste_real` (cascada de 6 niveles)

Se busca el precio del producto en este orden, usando el primero que devuelva valor > 0:

| Nivel | Fuente | Fórmula |
|---|---|---|
| 1 | **PO recibidas** | `SUM(price_unit × qty_received) / SUM(qty_received)` — media ponderada de todas las POs en estado `purchase/done` con `qty_received > 0` |
| 2 | **Última PO confirmada** | `price_unit` de la PO más reciente en cualquier estado ≠ `cancel` |
| 3 | **BoM activo** | Suma recursiva de componentes (ver abajo) |
| 4 | **Media de la plantilla** | Misma fórmula que nivel 1 pero para todas las variantes del mismo template |
| 5 | **Proveedor** | Primer `seller_ids.price > 0` (ordenado por secuencia) |
| 6 | **Ficha producto** | `standard_price` |

Si ninguno tiene valor → `0.0` (`sin_coste`).

### Coste desde BoM (`_coste_desde_bom`, recursivo máx. 2 niveles)

```
coste_bom = 0

Para cada línea de componente en la BoM:
    comp_qty  = bom_line.product_qty / bom.product_qty
    comp_price = standard_price
              → media POs recibidas del componente
              → BoM del componente (recursivo, máx. profundidad 2)
    coste_bom += comp_qty × comp_price

Para cada operación en la BoM:
    hours      = op.time_cycle_manual / 60
    coste_bom += hours × (wc.costs_hour + wc.employee_costs_hour)
```

### Campo `apunts_valor_stock`

```
apunts_valor_stock = apunts_coste_real × qty_available
```

---

## 2. Precio de un componente para una OF concreta — `_apunts_get_product_cost`

Cascada usada internamente al calcular MP de una OF. El nivel 1 busca en POs **vinculadas a la OF específica** via el campo `fabricacion`:

| Nivel | Fuente |
|---|---|
| 1 | Media ponderada de POs con `fabricacion = esta_OF` en estado `purchase/done` |
| 2 | `product.standard_price` |
| 3 | Último `stock.move` de entrada (`picking_type.code = incoming`) con `price_unit > 0` |
| 4 | Media ponderada de todas las POs recibidas del producto |
| 5 | Última PO confirmada del producto |
| 6 | Tarifa del proveedor (`seller_ids`) |

---

## 3. Costes de una OF — `mrp.production`

### Piezas producidas

```
apunts_qty_done    = MAX(qty_produced, qty_producing)
apunts_qty_pending = MAX(product_qty − apunts_qty_done, 0)
```

El campo `qty_producing` recoge lo que el operario ha marcado en taller sin validar
parcial todavía. Se toma el mayor de los dos para reflejar el estado real.

### Minutos

```
apunts_min_total_plan  = SUM(workorder.duration_expected)    ← suma de todas las fases
apunts_min_unit_plan   = apunts_min_total_plan / product_qty

apunts_min_real_total  = SUM(workorder.duration)             ← suma de todas las fases
apunts_min_unit_real   = apunts_min_real_total / denominador
```

Denominador para min/pieza real (cascada para evitar división por 0):
`apunts_qty_done → qty_producing → product_qty`

---

### Materia Prima teórica — `_apunts_mp_total_planned`

```
MP_plan = 0
Para cada move_raw con estado ≠ cancel:
    precio  = _apunts_get_product_cost(componente, esta_OF)
    MP_plan += move.product_qty × precio
```

### Materia Prima real — `_apunts_mp_total_real`

Lógica JR: por cada producto se toma el **MAX** de dos fuentes para evitar doble conteo
y cubrir el caso donde el material está en taller pero el operario aún no ha consumido
en pantalla:

```
Para cada producto en move_raw (estado ≠ cancel):
    recibido_PO    = SUM(pol.price_subtotal × qty_received / product_qty)
                     para POs con fabricacion=esta_OF en estado purchase/done

    consumo_fisico = move.quantity × _apunts_get_product_cost(producto, OF)

    MP_real       += MAX(recibido_PO, consumo_fisico)

Además: productos con PO vinculada (fabricacion=esta_OF) que NO aparecen
en move_raw (servicios externos: mecanizado, pavonado, pintura, etc.)
se suman directamente con su importe recibido de la PO.
```

---

### Costes de MO y Máquina teóricos — `_apunts_workorder_totals_planned`

```
Para cada workorder de la OF:
    hours = duration_expected / 60

    coste_maquina += hours × wc.costs_hour
    coste_amort   += hours × wc.apunts_amort_hour

    # Tarifa operario (cascada):
    avg_hora = media(employee_ids.hourly_cost)  si hay empleados asignados y avg > 0
             → wc.employee_costs_hour           en caso contrario
    coste_mo += hours × avg_hora
```

### Costes de MO y Máquina reales — `_apunts_workorder_totals_real`

SQL sobre `mrp_workcenter_productivity`, filtrando **solo fichajes cerrados**
(`date_end IS NOT NULL`):

```sql
SELECT
    SUM(p.duration / 60.0
        * COALESCE(NULLIF(he.hourly_cost, 0), wc.employee_costs_hour, 0))  AS mo,
    SUM(p.duration / 60.0 * wc.costs_hour)                                 AS machine,
    SUM(p.duration / 60.0 * wc.apunts_amort_hour)                          AS amort
FROM   mrp_workcenter_productivity p
JOIN   mrp_workorder               wo ON wo.id = p.workorder_id
JOIN   mrp_workcenter              wc ON wc.id = p.workcenter_id
LEFT   JOIN hr_employee            he ON he.id = p.employee_id
WHERE  wo.production_id = <id_OF>
  AND  p.date_end IS NOT NULL
```

Cascada coste operario real: `hourly_cost del empleado (NULLIF 0) → employee_costs_hour del workcenter`.

---

### Totales de la OF

```
apunts_cost_total_planned = MP_plan + MO_plan + maquina_plan + amort_plan
apunts_cost_total_real    = MP_real + MO_real + maquina_real + amort_real
```

### Indicador BoM incompleta

```
apunts_bom_incompleta = (MP_real > 50 €) AND (MP_real > MP_plan × 1,5)
```

Se activa cuando el material real supera en más del 50% al teórico y supera los 50 €.
Causa típica: la BoM tiene componentes que faltan, servicios externos no incluidos
o cantidades simbólicas.

---

### Importe de venta vinculada — `_compute_apunts_sale_amount`

Solo cuenta SOs en estado `sale/done` **y** con entrega no completada
(`delivery_status ≠ full`).

Cascada para encontrar el SO vinculado a la OF:

| Vía | Cálculo |
|---|---|
| `sale_line_id` directo | `price_subtotal × (product_qty_OF / qty_so)` — proporcional a la cantidad de la OF |
| `sale_id` directo | `SUM(price_subtotal)` de líneas del SO que coinciden en producto |
| `x_studio_venta` (campo Studio JR) | ídem |
| `procurement_group_id.sale_id` | ídem |

---

### Márgenes y factor de cobertura

```
apunts_margen_of          = apunts_sale_amount − apunts_cost_total_planned
apunts_margen_pct         = apunts_margen_of / apunts_sale_amount

apunts_margen_real_of     = apunts_sale_amount − apunts_cost_total_real
apunts_margen_real_pct    = apunts_margen_real_of / apunts_sale_amount

apunts_margen_real_dudoso = (coste_real ≤ 0) AND (venta > 0)
                            ← OF sin fichajes, el margen real es artificial

apunts_factor_cobertura   = apunts_sale_amount / apunts_cost_total_real
                            (0 si coste_real = 0)
```

Semáforo del factor de cobertura (objetivo JR: ≥ 1,35):

| Color | Condición |
|---|---|
| Verde | factor ≥ 1,35 |
| Ámbar | 1,0 ≤ factor < 1,35 |
| Rojo | factor < 1,0 (pérdidas) |
| Sin color | factor = 0 (sin datos reales) |

---

### Criterio WIP — `apunts_is_wip`

Una OF se considera **en curso (WIP)** si cumple **todo**:

1. Estado en `confirmed / progress / to_close`
2. `qty_done < product_qty` (no producida del todo)
3. Al menos una de las dos condiciones siguientes:
   - Tiene consumo físico en algún `move_raw` (`quantity > 0`)
   - Tiene una PO con `fabricacion = esta_OF` en estado `purchase/done` con `qty_received > 0`

---

## 4. Resumen global WIP — `apunts.wip.resumen`

Agrega los campos de **todas** las OFs donde `apunts_is_wip = True`:

| Campo | Cálculo |
|---|---|
| `n_ofs_wip` | COUNT de OFs WIP |
| `total_venta` | SUM(`apunts_sale_amount`) |
| `total_mat_planned / real` | SUM de MP teórica / real |
| `total_mo_planned / real` | SUM de coste operario teórico / real |
| `total_machine_planned / real` | SUM de coste máquina teórico / real |
| `total_min_planned` | SQL: `SUM(wo.duration_expected)` de fases de OFs WIP |
| `total_min_real` | SQL: `SUM(p.duration)` de fichajes cerrados (`date_end IS NOT NULL`) de OFs WIP |
| `total_horas_planned / real` | `total_min / 60` |
| `total_jornadas_planned / real` | `total_horas / 8` (jornada de 8 horas) |
| `total_cost_planned / real` | SUM de coste total teórico / real |
| `n_ofs_bom_incompleta` | COUNT donde `apunts_bom_incompleta = True` |
| `total_mat_planned_ajustado` | Por OF: si BoM incompleta → usa `mat_real`; si no → usa `mat_plan` |
| `margen_estimado` | `total_venta − total_cost_planned` |
| `total_mp_pendiente_recibir` | SQL: `SUM((product_qty − qty_received) × price_unit)` de POs con `fabricacion IN <wip_ids>` pendientes de recibir |

### SQL para minutos del resumen

```sql
-- Minutos teóricos
SELECT COALESCE(SUM(wo.duration_expected), 0)
FROM mrp_workorder wo
WHERE wo.production_id IN (<wip_ids>)

-- Minutos reales
SELECT COALESCE(SUM(p.duration), 0)
FROM mrp_workcenter_productivity p
JOIN mrp_workorder w ON w.id = p.workorder_id
WHERE w.production_id IN (<wip_ids>)
  AND p.date_end IS NOT NULL
```

### SQL para MP pendiente de recibir

```sql
SELECT COALESCE(SUM((pol.product_qty - pol.qty_received) * pol.price_unit), 0)
FROM purchase_order_line pol
JOIN purchase_order po ON po.id = pol.order_id
WHERE pol.fabricacion IN (<wip_ids>)
  AND po.state IN ('purchase', 'done')
  AND pol.qty_received < pol.product_qty
```

---

## 5. Centro de trabajo — `mrp.workcenter`

Campo añadido:

| Campo | Descripción |
|---|---|
| `apunts_amort_hour` | Coste de amortización por hora (€). Se suma al coste de máquina en el cálculo de costes de la OF. |

---

## 6. Reactividad — `purchase.order.line`

El módulo intercepta `write` y `create` en líneas de compra para recalcular automáticamente
cuando cambian datos relevantes, **sin esperar al cron ni a una actualización manual**:

| Campos que disparan el recálculo | Qué se recalcula |
|---|---|
| `qty_received`, `fabricacion`, `price_unit`, `price_subtotal`, `product_qty` | Campos `apunts_*` de la OF vinculada (`fabricacion`) |
| `qty_received`, `price_unit`, `price_subtotal`, `product_id` | `apunts_coste_real` y `apunts_coste_fuente` de los productos afectados |

El recálculo se hace tanto al **crear** nuevas líneas de compra como al **modificar** las existentes.
