# Lira Financial Suite — Documentación Técnica
**Módulo: lira_dashboard_contabilidad** · Odoo 18

---

## Índice

1. [Arquitectura general](#1-arquitectura-general)
2. [Dashboard KPIs](#2-dashboard-kpis)
3. [Análisis de Ventas](#3-análisis-de-ventas)
4. [Escandallo de Costes](#4-escandallo-de-costes)
5. [Margen por Cliente](#5-margen-por-cliente)
6. [Previsión de Liquidez](#6-previsión-de-liquidez)
7. [Previsión de Salarios](#7-previsión-de-salarios)
8. [Existencias y Aprovisionamientos](#8-existencias-y-aprovisionamientos)
9. [Calculadora VAN / TIR](#9-calculadora-van--tir)
10. [Requisitos para que los datos sean correctos](#10-requisitos-para-que-los-datos-sean-correctos)

---

## 1. Arquitectura general

### Tipos de modelo

| Sección | Modelo Python | Tipo | Persistencia |
|---|---|---|---|
| Dashboard KPIs | `lira.dashboard` | TransientModel | ~1 hora (auto-borrado Odoo) |
| Análisis de Ventas | `lira.sales.analysis` | TransientModel | ~1 hora |
| Escandallo de Costes | `lira.product.costing` | TransientModel | ~1 hora |
| Margen por Cliente | `lira.customer.margin` | TransientModel | ~1 hora |
| Previsión de Liquidez | `lira.forecast` | **Model** | Permanente hasta recalcular |
| Previsión de Salarios | `lira.salary.forecast` | TransientModel | ~1 hora |
| Existencias | `lira.stock.valuation` | TransientModel | ~1 hora |
| **Calculadora VAN/TIR** | `lira.van.tir` | **Model** | **Permanente, nunca se borra** |

> Los modelos `TransientModel` son temporales — Odoo los elimina automáticamente tras ~1 hora. Cada vez que abres el menú se crea un registro nuevo con los datos recalculados en ese momento.
>
> Los modelos `Model` son permanentes. El VAN/TIR en particular **nunca se borra** — los proyectos de inversión quedan guardados indefinidamente.

### Fuente de datos principal

Todos los cálculos financieros leen de `account.move.line` (asientos contables) con:
- `move_id.state = 'posted'` → solo asientos validados
- `move_id.move_type = 'out_invoice'` → solo facturas de cliente (donde aplique)

---

## 2. Dashboard KPIs

**Modelo:** `lira.dashboard` · **Método principal:** `_compute_all()`

### Fuente de datos: consulta SQL única

Para evitar múltiples queries, el dashboard ejecuta **una sola consulta SQL con GROUP BY** que devuelve tres diccionarios:
- `by_type` → clave = `account_type` de Odoo (ej. `asset_receivable`)
- `by_code2` → clave = primeros 2 dígitos del código contable (ej. `'64'`, `'62'`)
- `by_code1` → clave = primer dígito (ej. `'3'` para existencias)

```sql
SELECT aa.account_type,
       LEFT(aa.code_store->>'1', 2) AS c2,
       LEFT(aa.code_store->>'1', 1) AS c1,
       SUM(aml.debit) - SUM(aml.credit) AS net
FROM   account_move_line aml
JOIN   account_account   aa ON aa.id = aml.account_id
JOIN   account_move      am ON am.id = aml.move_id
WHERE  am.state = 'posted'
  AND  aml.company_id = {empresa}
  AND  aml.date BETWEEN {fecha_desde} AND {fecha_hasta}
GROUP  BY aa.account_type, c2, c1
```

El balance de situación usa la misma query **sin filtro de fecha** (foto del momento actual).

### Cuenta de resultados — cuentas del PGC utilizadas

| Concepto | Código PGC | Cómo se calcula |
|---|---|---|
| Ventas del periodo | `70x` | `-(net del grupo 70)` — negado porque son cuentas acreedoras |
| Otros ingresos explotación | `71x, 73x, 74x, 75x` | `-(net de 71+73+74+75)` |
| **Ingresos de explotación** | `70x–75x` | Ventas + Otros ingresos |
| Coste de ventas (COGS) | `60x, 61x` | `net de 60 + net de 61` |
| **Beneficio bruto** | — | Ingresos explotación − Coste ventas |
| Gastos de personal | `64x` | `net de 64` |
| Gastos generales | `62x, 63x, 65x` | `net de 62 + 63 + 65` |
| **EBITDA** | — | Beneficio bruto − Personal − Generales |
| Amortizaciones | `68x` | `net de 68` |
| **EBIT** | — | EBITDA − Amortizaciones |
| Resultado financiero | `76x, 66x` | `-(net 76) - (net 66)` |
| **Beneficio neto (BAI)** | — | EBIT + Resultado financiero |

### Balance de situación — cuentas del PGC utilizadas

| Partida | account_type Odoo | Notas |
|---|---|---|
| Clientes | `asset_receivable` | Net positivo |
| Tesorería | `asset_cash` | Net positivo |
| Activo corriente | `asset_receivable + asset_cash + asset_current` | |
| Activo no corriente | `asset_non_current + asset_fixed` | |
| Proveedores | `liability_payable` | Net negado |
| Pasivo corriente | `liability_payable + liability_current` | Net negado |
| Pasivo no corriente | `liability_non_current` | Net negado |
| Patrimonio neto | — | Activo total − Pasivo total |
| Existencias | Primer dígito `'3'` | Grupo 3 del PGC (300xxx–399xxx) |

### Ratios financieros — fórmulas exactas

| Ratio | Fórmula | Verde | Amarillo | Rojo |
|---|---|---|---|---|
| Liquidez general | Activo corriente / Pasivo corriente | ≥ 1,5 | ≥ 1,0 | < 1,0 |
| Liquidez inmediata | (Activo cte. − Existencias) / Pasivo cte. | ≥ 1,0 | ≥ 0,7 | < 0,7 |
| Tesorería | Tesorería / Pasivo corriente | ≥ 0,3 | ≥ 0,1 | < 0,1 |
| Solvencia | Activo total / Pasivo total | ≥ 2,0 | ≥ 1,2 | < 1,2 |
| Endeudamiento | Pasivo total / Activo total × 100 | ≤ 40% | ≤ 60% | > 60% |
| ROE | Beneficio neto / Patrimonio neto × 100 | ≥ 10% | ≥ 5% | < 5% |
| ROA | Beneficio neto / Activo total × 100 | ≥ 5% | ≥ 2% | < 2% |
| Margen bruto | Beneficio bruto / Ingresos × 100 | ≥ 30% | ≥ 15% | < 15% |
| Margen EBITDA | EBITDA / Ingresos × 100 | ≥ 15% | ≥ 5% | < 5% |
| Margen neto | Beneficio neto / Ingresos × 100 | ≥ 8% | ≥ 2% | < 2% |

### Ciclo de maduración — fórmulas exactas

| Indicador | Fórmula | Campo Odoo |
|---|---|---|
| PMC (Periodo Medio de Cobro) | (Saldo clientes / Ventas) × días del periodo | `asset_receivable` / `ingresos_op` |
| PMP (Periodo Medio de Pago) | (Saldo proveedores / COGS) × días del periodo | `liability_payable` / `coste_v` |
| PMA (Periodo Medio de Almacén) | (Existencias / COGS) × días del periodo | grupo `3` / `coste_v` |
| Ciclo de caja | PMC + PMA − PMP | — |

### Variación vs. periodo anterior

El sistema calcula automáticamente un **periodo anterior** de la misma duración inmediatamente antes del periodo seleccionado:
- Periodo actual: `date_from` → `date_to`
- Periodo anterior: `(date_from - duración - 1 día)` → `(date_from - 1 día)`

La variación se muestra como flecha: `↑ +5,2%` / `↓ -3,1%` / `→ +0,5%` (umbral ±2%).

### Layout del formulario — orden de secciones

```
1. Cabecera KPIs (header)
2. Liquidez y solvencia
3. Rentabilidad
4. Cuenta de resultados + Balance de situación
5. Ciclo de maduración
6. Alertas del periodo  ← al final, solo visibles si hay_alertas = True
```

El bloque de alertas (`ld_alerts_panel`) está al final del `<sheet>` para no interrumpir la lectura de los KPIs principales. Se oculta automáticamente si no hay ninguna alerta activa.

### Diseño de tarjetas (ratio cards)

Las tarjetas de ratios usan CSS compacto para caber 10 en pantalla sin scroll:
- `.ld_ratio_card`: `flex: 1 1 128px; min-width: 115px`
- `.ld_card_body`: `padding: 9px 11px`
- `.ld_card_label`: `font-size: 0.72rem; color: var(--ld-ink2)` — etiqueta en oscuro para legibilidad
- `.ld_card_value`: `font-size: 1.35rem` — número compacto
- `.ld_ratio_row` gap: `8px`

---

## 3. Análisis de Ventas

**Modelo:** `lira.sales.analysis` · **Método principal:** `_do_compute()`

> **Base imponible**: todos los importes usan `price_subtotal` (sin IVA), por requisito del contable. La única excepción del módulo es la Previsión de Liquidez, que usa importes con IVA incluido.

### Filtro de líneas de pedido

```python
sale.order.line donde:
  order_id.state IN ('sale', 'done')       # Solo pedidos confirmados
  order_id.date_order BETWEEN desde/hasta
  order_id.company_id = empresa actual
```

### Cálculo del importe por línea

```python
importe = line.price_subtotal  # Base imponible sin IVA
```

### Buscador nativo ("Explorar tabla")

El botón **Explorar tabla** abre las `sale.order.line` con dominio de fecha aplicado y una vista de búsqueda propia (`view_lira_sale_line_search`) que ofrece:

| Agrupación | Campo Odoo |
|---|---|
| Semana | `order_id.date_order:week` |
| Mes | `order_id.date_order:month` |
| Trimestre | `order_id.date_order:quarter` |
| Año | `order_id.date_order:year` |
| Producto | `product_id` |
| Cliente | `order_partner_id` |
| Vendedor | `salesman_id` |

Por defecto se aplica `search_default_group_mes: 1` (agrupado por mes al abrir).

### Agrupaciones disponibles

| Agrupación | Clave | Label |
|---|---|---|
| Por producto | `product_id.id` | `product_id.display_name` |
| Por cliente | `partner_id.commercial_partner_id.id` | Nombre empresa matriz |
| Por categoría | `product_id.categ_id.id` | `categ_id.name` |
| Por mes | `invoice_date.strftime('%Y-%m')` | `invoice_date.strftime('%b %Y')` |
| Por vendedor | `invoice_user_id.id` | `invoice_user_id.name` |

> La agrupación por cliente usa **`commercial_partner_id`** (empresa matriz) para consolidar todos los contactos y delegaciones del mismo grupo bajo un único nombre.

### Columnas calculadas

| Columna | Fórmula |
|---|---|
| Ventas (€) | `sum(credit - debit)` de las líneas del grupo |
| Unidades | `sum(quantity)` de las líneas del grupo |
| Facturas | `len(set(move_id))` — número de facturas distintas |
| Ticket medio (€) | Ventas (€) / Número de facturas |
| % s/total | (Ventas del grupo / Total ventas) × 100 |
| Último pedido | `max(invoice_date)` del grupo |

### KPIs del encabezado

| KPI | Cálculo |
|---|---|
| Total ventas | Suma de todos los grupos con importe > 0 |
| Clientes activos | `len(set(commercial_partner_id))` de todas las líneas |
| Productos vendidos | `len(set(product_id))` de las líneas con producto |
| Top producto | Primer elemento del ranking (mayor importe) |
| Top cliente | Cliente con mayor suma `credit - debit` en el periodo |

---

## 4. Escandallo de Costes

**Modelo:** `lira.product.costing` · **Método principal:** `_do_compute()`

### Filtro de líneas

Igual que Análisis de Ventas pero **solo líneas con producto** (`product_id != False`).

### Cálculo por producto

| Campo | Fórmula | Fuente Odoo |
|---|---|---|
| Uds. vendidas | `sum(quantity)` | `account.move.line.quantity` |
| PVP medio (€) | Ventas totales / Uds. vendidas | Calculado |
| Coste unitario (€) | `product.standard_price` | `product.product.standard_price` |
| Margen unitario (€) | PVP medio − Coste unitario | Calculado |
| Ventas totales (€) | `sum(credit - debit)` | `account.move.line` |
| Coste total (€) | Coste unitario × Uds. vendidas | Calculado |
| Margen total (€) | Ventas totales − Coste total | Calculado |
| Margen (%) | (Margen total / Ventas totales) × 100 | Calculado |

> **El coste siempre es el `standard_price` del producto en el momento del cálculo**, no el coste histórico en el momento de la venta. Si el coste ha cambiado desde que se hizo la venta, el escandallo refleja el coste actual, no el de la operación original.

### Semáforo de alerta

```python
if margen_pct < umbral_critico:  alerta = 'critico'   # Rojo
elif margen_pct < umbral_bajo:   alerta = 'medio'     # Naranja
else:                             alerta = 'ok'        # Verde
```

Valores por defecto: `umbral_bajo = 20%`, `umbral_critico = 5%`. Configurables por el usuario.

---

## 5. Margen por Cliente

**Modelo:** `lira.customer.margin` · **Método principal:** `_do_compute()`

### Filtro de líneas

Igual que Escandallo: facturas validadas en el periodo, cuentas de ingresos, solo líneas con producto. Opcionalmente filtrado por un cliente concreto.

### Agrupación

Agrupa por `commercial_partner_id` para consolidar todas las delegaciones y contactos bajo la empresa matriz.

### Cálculo por cliente

| Campo | Fórmula | Fuente Odoo |
|---|---|---|
| Facturado (€) | `sum(credit - debit)` de las líneas | `account.move.line` |
| Coste estimado (€) | `sum(standard_price × quantity)` | `product.product.standard_price` × `account.move.line.quantity` |
| Margen (€) | Facturado − Coste estimado | Calculado |
| Margen (%) | (Margen / Facturado) × 100 | Calculado |
| Facturas | `len(set(move_id))` | Calculado |
| Último pedido | `max(invoice_date)` | `account.move.invoice_date` |

### KPIs del encabezado

| KPI | Cálculo |
|---|---|
| Total facturado | Suma de `facturado` de todos los clientes |
| Margen total | Suma de `margen_euros` |
| Margen medio % | (Margen total / Total facturado) × 100 |
| Mejor cliente | Cliente con mayor `facturado` |
| Cliente a revisar | Cliente con menor `margen_pct` |

---

## 6. Previsión de Liquidez

**Modelo:** `lira.forecast` (Model permanente) · **Método:** `_generate_forecast()`

> Este módulo **borra todos los registros anteriores y recalcula desde cero** cada vez que se abre el menú. Los datos son una estimación a 6 meses vista.

### Cálculo de bases históricas

Para cada uno de los últimos 3 meses se calcula:

```python
# Ingresos mensuales medios
account.move.line donde:
  account_id.account_type IN ('income', 'income_other')
  move_id.state = 'posted'
  date BETWEEN inicio_mes AND fin_mes
→ importe = abs(sum(debit - credit))

# Gastos mensuales medios
account.move.line donde:
  account_id.account_type IN ('expense', 'expense_direct_cost')
  move_id.state = 'posted'
  date BETWEEN inicio_mes AND fin_mes
→ importe = abs(sum(debit - credit))
```

### Desglose fijo/variable (heurística)

| Componente | Porcentaje aplicado |
|---|---|
| Ingresos fijos | 60% de la media de ingresos |
| Ingresos variables | 40% de la media de ingresos |
| Gastos fijos | 55% de la media de gastos |
| Gastos variables | 45% de la media de gastos |

### Ajuste por pendientes reales

- **Ingresos variables extra:** pedidos confirmados sin facturar (`sale.order` con `state IN ('sale','done')` e `invoice_status = 'to invoice'`) divididos entre 6 meses.
- **Gastos variables extra:** facturas de proveedor pendientes de pago (`account.move` tipo `in_invoice`, validadas, `payment_state IN ('not_paid','partial')`) divididas entre 6 meses.

---

## 7. Previsión de Salarios

**Modelo:** `lira.salary.forecast` · **Método principal:** `_do_compute()`

### Datos históricos — cuentas del PGC

| Concepto | Cuenta PGC | Cómo se lee |
|---|---|---|
| Salarios brutos | `640` | `sum(debit - credit)` de líneas en cuenta `640%` |
| Otros gastos personal | `641, 642, 643, 649` | Suma de los cuatro grupos |
| Seguridad Social empresa (estimada) | — | `salarios_640 × tasa_ss / 100` |
| Total mes real | — | Salarios + SS estimada + Otros |

> La SS empresa se **estima** a partir de los salarios brutos y la tasa configurada. No se lee directamente de la cuenta 642 para la estimación (la 642 sí se suma en "otros" si está contabilizada).

### Proyección futura

```python
media_mensual = promedio(total_mes) de los últimos N meses históricos
factor_mensual = (1 + incremento_anual_pct / 100) ** (1/12)

# Para cada mes futuro i:
previsto_i = media_mensual × (factor_mensual ** i)
salario_bruto_i = previsto_i / (1 + tasa_ss / 100)
ss_i = salario_bruto_i × tasa_ss / 100
```

---

## 8. Existencias y Aprovisionamientos

**Modelo:** `lira.stock.valuation` · **Método principal:** `_do_compute()`

### Fuentes de datos

| Dato | Modelo Odoo | Filtro |
|---|---|---|
| Stock actual | `stock.quant` | `location_id.usage = 'internal'` |
| Consumo histórico | `stock.move` | `state = 'done'`, `location_dest_id.usage = 'customer'`, fecha en el rango de meses configurado |
| Coste unitario | `product.product.standard_price` | — |

### Cálculo por producto

| Campo | Fórmula |
|---|---|
| Stock actual | `sum(stock.quant.quantity)` en ubicaciones internas |
| Consumo mensual | `sum(stock.move.product_qty)` / meses configurados |
| Valor stock (€) | Stock actual × `standard_price` |
| Cobertura (meses) | Stock actual / Consumo mensual (99 si consumo = 0) |
| Punto de reorden | Consumo mensual × Cobertura mínima × 1,5 |

### Semáforo de estado

```python
if qty <= 0:                              estado = 'critico'
elif cobertura < meses_cobertura_min:     estado = 'bajo'
elif cobertura > meses_cobertura_max:     estado = 'exceso'
else:                                     estado = 'ok'
```

---

## 9. Calculadora VAN / TIR

**Modelo:** `lira.van.tir` (Model permanente) · **Método:** `action_calcular()` → `_calcular()`

> Los proyectos de inversión **se guardan permanentemente** en la base de datos y nunca se borran automáticamente.

### Flujo de uso

1. Entrar en "Calculadora VAN / TIR" → aparece la lista de proyectos guardados.
2. Pulsar **Nuevo** para crear un proyecto nuevo (se abre el formulario).
3. Rellenar **Inversión inicial**, **Tasa de descuento** y **Valor residual** en la barra superior.
4. Introducir los **ingresos y gastos esperados** en cada fila de la tabla anual.
5. Pulsar el botón **Calcular** → los resultados se guardan en la base de datos.

> **Importante:** el campo "Flujo neto" de cada fila se calcula automáticamente (`Ingresos - Gastos`). Para que el VAN y la TIR sean correctos, hay que rellenar los ingresos en la tabla — si se deja todo a 0, el VAN será igual a −Inversión inicial.

### Fórmulas de cálculo

#### VAN (Valor Actual Neto)

```
flujos = [-inversión_inicial, flujo_año_1, flujo_año_2, ..., flujo_año_N + valor_residual]
r = tasa_descuento / 100

VAN = sum( flujos[t] / (1 + r)^t  para t = 0, 1, ..., N )
```

#### TIR (Tasa Interna de Retorno)

Calculada por **bisección numérica** (200 iteraciones, precisión 0,01€):
```
TIR = tasa r tal que VAN(r) = 0
Rango de búsqueda: [-99,99%, +10.000%]
```

#### Payback

```
Año en que el flujo acumulado pasa de negativo a positivo.
Si nunca se recupera: payback = número total de años.
Fracción de año: abs(acumulado_previo) / flujo_del_año_de_cruce
```

#### Índice de rentabilidad

```
IR = sum( flujos_positivos[t] / (1+r)^t ) / inversión_inicial
IR > 1 → la inversión genera más valor del que consume
```

### Tabla de decisión automática

| Condición | Decisión | Color |
|---|---|---|
| VAN > 0 y TIR > tasa | VIABLE | Verde |
| VAN > 0 pero TIR ≤ tasa | ACEPTABLE | Amarillo |
| VAN negativo pero > −10% de la inversión | MARGINAL | Amarillo |
| VAN < −10% de la inversión | NO VIABLE | Rojo |

---

## 10. Requisitos para que los datos sean correctos

### Para el Dashboard KPIs y la Cuenta de Resultados

- Las facturas de cliente deben estar **validadas** (`estado = Publicado`).
- Las líneas de venta deben contabilizarse en cuentas del **grupo 70x** (ventas de mercaderías y servicios).
- Los costes de compra deben ir a **grupo 60x** (compras) o **61x** (variación de existencias).
- Los salarios a **640**, la seguridad social a **642**, otros gastos de personal a **641/643/649**.
- Las amortizaciones a **68x**.
- Los gastos financieros a **66x**, los ingresos financieros a **76x**.

### Para el Escandallo y el Margen por Cliente

- El **precio de coste** (`standard_price`) de cada producto debe mantenerse actualizado en la ficha del producto (Inventario → Productos → pestaña "Información general").
- Si el coste del producto cambia con el tiempo, el escandallo refleja siempre el coste **actual** en el momento del cálculo, no el histórico.

### Para la Previsión de Salarios

- Las nóminas deben estar contabilizadas mensualmente en las cuentas del **grupo 64**.
- Sin asientos en 640, la previsión histórica mostrará 0.

### Para Existencias y Aprovisionamientos

- Los movimientos de stock deben estar validados (`estado = Hecho`).
- El **precio de coste estándar** del producto debe estar actualizado.
- Sin movimientos de salida hacia clientes, el consumo mensual será 0 y la cobertura aparecerá como 99 meses.

### Para la Calculadora VAN / TIR

- Los flujos son manuales — no vienen de Odoo. El usuario introduce los ingresos y gastos esperados por año.
- La tasa de descuento debe reflejar el coste real del capital de la empresa (habitualmente entre el 8% y el 12%).

---

*Lira Financial Suite · Documentación técnica interna · Odoo 18 · © 2025*
