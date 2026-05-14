# Lira Financial Suite — Guía de Usuario
**Módulo: Análisis Financiero** · Odoo 18

---

## ¿Qué es este módulo?

El módulo **Análisis Financiero** añade un menú completo dentro de Contabilidad que permite al CEO y al responsable financiero ver en tiempo real la salud económica de la empresa. Todos los datos se calculan automáticamente a partir de los asientos contables, facturas y movimientos de almacén registrados en Odoo — sin necesidad de exportar a Excel.

---

## Acceso

**Contabilidad → Análisis Financiero** (menú lateral)

Dentro encontrarás 8 secciones:

| Sección | Para qué sirve |
|---|---|
| Dashboard KPIs | Resumen financiero completo del periodo |
| Análisis de Ventas | Ranking de ventas por producto / cliente / categoría |
| Escandallo de Costes | Rentabilidad real de cada producto |
| Margen por Cliente | Qué clientes te generan más beneficio |
| Previsión de Liquidez | Gráfico de tesorería a 6 meses |
| Previsión de Salarios | Gasto de personal histórico + proyección |
| Existencias y Aprovisionamientos | Control de stock y alertas de reposición |
| Calculadora VAN / TIR | Análisis de viabilidad de inversiones |

---

## 1 · Dashboard KPIs

### Cómo usarlo
1. Abre **Dashboard KPIs**.
2. Ajusta las fechas **Desde / Hasta** en la cabecera para seleccionar el periodo.
3. Pulsa **Actualizar** para recalcular todos los datos.

### Qué verás

**Barra superior (KPIs de un vistazo)**
- **Ventas del periodo** — suma de todas las facturas de cliente validadas en el rango de fechas
- **EBITDA** — beneficio operativo antes de amortizaciones
- **Beneficio neto** — resultado final del periodo
- **Margen bruto %** — porcentaje de beneficio bruto sobre ingresos

**Alertas inteligentes** (aparecen solo si hay algo que revisar)
- Rojo: situación crítica que requiere acción inmediata
- Naranja: indicador por debajo del umbral óptimo
- Verde: indicador en rango saludable

**Liquidez y solvencia** (5 ratios con semáforo)

| Ratio | Fórmula | Óptimo |
|---|---|---|
| Liquidez general | Activo corriente / Pasivo corriente | > 1,5 |
| Liquidez inmediata | (Activo cte. − Existencias) / Pasivo cte. | > 1,0 |
| Tesorería | Tesorería / Pasivo corriente | > 0,3 |
| Solvencia | Activo total / Pasivo total | > 2,0 |
| Endeudamiento | Pasivo total / Activo total × 100 | < 50% |

**Cuenta de resultados** — muestra la cascada completa:

```
Ingresos de explotación       (cuentas 70x + 71x + 73x + 74x + 75x)
− Coste de ventas             (cuentas 60x + 61x)
= Beneficio bruto
− Gastos de personal          (cuentas 64x)
− Gastos generales            (cuentas 62x + 63x + 65x)
= EBITDA
− Amortizaciones              (cuentas 68x)
= EBIT (Resultado de explotación)
± Resultado financiero        (76x − 66x)
= Beneficio neto (BAI)
```

> **Importante para la venta:** el margen de cada venta contribuye directamente a los ingresos de explotación. Para que el dashboard muestre datos correctos, cada factura debe tener:
> - La **línea de venta** contabilizada en una cuenta del grupo 70x (ventas)
> - El **coste del producto** actualizado en la ficha del producto (campo "Coste" en la pestaña de información general)

**Balance de situación** — lado derecho siempre igual al izquierdo:
```
Activo total = Patrimonio neto + Pasivo no corriente + Pasivo corriente
```

**Ciclo de maduración**
- **PMC** (Periodo Medio de Cobro): días de media que tardan los clientes en pagar
- **PMP** (Periodo Medio de Pago): días de media que tardas en pagar a proveedores
- **PMA** (Periodo Medio de Almacén): días que permanece el stock en almacén
- **Ciclo de caja** = PMC + PMA − PMP (cuanto más negativo, mejor)

---

## 2 · Análisis de Ventas

### Cómo usarlo
1. Selecciona el periodo con las fechas.
2. Elige **Agrupar por**: Producto, Cliente o Categoría.
3. Pulsa **Actualizar**.

### Qué verás
Ranking ordenado de mayor a menor margen con código de color:
- 🟢 Verde: margen ≥ 25%
- 🟡 Naranja: margen entre 10% y 25%
- 🔴 Rojo: margen < 10%

### Qué datos entran en el cálculo
- **Ventas (€)**: suma de `credit − debit` de las líneas de factura de cliente validadas, en cuentas de tipo "ingresos" (`account_type = income / income_other`), para productos identificados
- **Coste (€)**: `precio_coste_estándar × unidades_vendidas` (campo "Coste" de la ficha del producto en Odoo)
- **Margen**: Ventas − Coste

> Para que el coste sea correcto, mantén actualizado el **Precio de Coste** en cada ficha de producto (Inventario → Productos → pestaña "Información general").

---

## 3 · Escandallo de Costes

### Cómo usarlo
1. Selecciona el periodo.
2. Ajusta los umbrales de alerta:
   - **Umbral bajo**: margen por debajo del cual el producto se marca en naranja (defecto: 20%)
   - **Umbral crítico**: margen por debajo del cual se marca en rojo (defecto: 5%)
3. Pulsa **Actualizar**.

### Qué verás
Una tabla por producto con:
- PVP medio facturado (`Ventas € / Unidades`)
- Coste unitario (precio de coste de la ficha de producto)
- Margen unitario y margen % sobre ventas
- Semáforo de alerta: OK / Margen bajo / Margen crítico

### Datos que entran al hacer una venta
Cuando se valida una factura de cliente:
- El **PVP medio** se actualiza con el precio facturado
- El **coste** se toma del campo `standard_price` del producto en el momento del cálculo
- Si el coste real es diferente al coste estándar (p. ej. porque cambiaste proveedores), actualiza el precio de coste del producto para que el escandallo refleje la realidad

---

## 4 · Margen por Cliente

### Cómo usarlo
1. Selecciona el periodo.
2. Opcionalmente filtra por un cliente concreto.
3. Pulsa **Actualizar**.

### Qué verás
Tabla de clientes ordenada de mayor a menor rentabilidad:
- **Facturado**: total de facturas validadas al cliente
- **Coste estimado**: suma de `coste_estándar × uds` de todos los productos facturados
- **Margen €** y **Margen %**
- Fecha del último pedido y número de facturas

> Un cliente con mucho volumen pero margen < 10% puede estar lastrando la rentabilidad general. Esta vista permite detectarlo de inmediato.

---

## 5 · Previsión de Liquidez

### Qué verás
Gráfico de barras y tabla con la tesorería prevista mes a mes durante 6 meses. Los datos proceden de:
- Facturas pendientes de cobro
- Pagos pendientes a proveedores
- Patrones históricos de cobro y pago

Útil para anticipar meses con tensión de tesorería.

---

## 6 · Previsión de Salarios

### Cómo usarlo
1. Define cuántos meses históricos mostrar y cuántos meses proyectar.
2. Indica el **incremento anual %** para la previsión (ej. 3% = incremento salarial esperado).
3. Indica la **tasa de Seguridad Social empresa** (defecto: 29,9%).
4. Pulsa **Actualizar**.

### Datos históricos (qué coge de Odoo)
Los datos reales se extraen de las cuentas contables:
- **640** – Sueldos y salarios
- **641, 642, 643, 649** – Otros gastos de personal (seguridad social, dietas, formación, etc.)

La Seguridad Social de empresa se estima como `salarios_brutos × tasa_ss / 100`.

> Para obtener datos correctos, las nóminas deben estar contabilizadas mensualmente en las cuentas del grupo 64.

---

## 7 · Existencias y Aprovisionamientos

### Cómo usarlo
1. Ajusta los parámetros:
   - **Consumo (meses)**: periodo para calcular el consumo medio mensual
   - **Cobertura mínima**: meses de stock mínimo antes de alertar
   - **Alerta exceso**: meses de stock a partir de los cuales se considera exceso
2. Pulsa **Actualizar**.

### Semáforo de stock

| Estado | Significado |
|---|---|
| 🟢 OK | Stock dentro del rango óptimo |
| 🟡 Bajo | Por debajo de la cobertura mínima configurada |
| 🔴 Crítico | Sin stock o stock cero |
| 🔵 Exceso | Por encima del límite de exceso configurado |

### Qué datos entran
- **Stock actual**: `stock.quant` en ubicaciones internas
- **Consumo mensual**: movimientos `stock.move` completados hacia clientes, promediado por los meses configurados
- **Coste unitario**: `standard_price` del producto
- **Punto de reorden**: `consumo_mensual × cobertura_mínima × 1,5`

---

## 8 · Calculadora VAN / TIR

### Cómo usarlo
1. Introduce el nombre y descripción de la inversión.
2. Indica la **Inversión inicial**, el **Valor residual** al final y la **Tasa de descuento** (coste del capital, normalmente entre 8% y 12%).
3. En la tabla de flujos, añade una fila por año con los ingresos y gastos previstos.
4. Los resultados se calculan automáticamente.

### Interpretación de resultados

| Indicador | Cuándo es buena señal |
|---|---|
| VAN > 0 | La inversión genera valor por encima del coste del capital |
| TIR > tasa de descuento | La rentabilidad supera el umbral mínimo exigido |
| Payback < vida útil | Se recupera la inversión dentro del horizonte temporal |
| Índice de rentabilidad > 1 | Por cada euro invertido se genera más de 1€ de valor |

---

## Preguntas frecuentes

**¿Por qué el EBITDA es negativo si vendo bastante?**
Los gastos operativos (personal + gastos generales) superan el margen bruto. Revisa la sección "Distribución de costes" para ver qué partida consume más.

**¿Por qué el balance no cuadra?**
Si ves diferencia entre Activo total y Total Pasivo+PN, revisa que todos los asientos de apertura de balance estén correctamente contabilizados en Odoo.

**¿Cada cuánto se actualiza el dashboard?**
Los datos NO se actualizan en tiempo real. Siempre hay que pulsar **Actualizar** para recalcular con los últimos datos. Se recomienda hacerlo cada mañana al inicio del día.

**¿Qué significa que un producto aparezca rojo en el escandallo?**
Que el margen real de ese producto está por debajo del umbral crítico configurado (defecto 5%). Puede ser porque el precio de venta es bajo, el coste es alto, o el coste estándar en la ficha del producto no está actualizado.

**¿Qué entra en el coste de una venta?**
El módulo usa el **precio de coste estándar** (`standard_price`) del producto en Odoo, multiplicado por las unidades vendidas. No incluye gastos de envío, descuentos de compra ni variaciones de coste posteriores a la venta. Para máxima precisión, mantén el precio de coste actualizado en cada ficha de producto.

---

## Glosario rápido

| Término | Definición |
|---|---|
| PGC | Plan General Contable (normativa contable española) |
| EBITDA | Earnings Before Interest, Taxes, Depreciation and Amortization — beneficio operativo antes de amortizaciones |
| EBIT | Earnings Before Interest and Taxes — beneficio operativo después de amortizaciones |
| BAI | Beneficio Antes de Impuestos (equivale al "Beneficio neto" mostrado en el dashboard) |
| ROE | Return on Equity — rentabilidad sobre el patrimonio neto |
| ROA | Return on Assets — rentabilidad sobre el activo total |
| PMC | Periodo Medio de Cobro |
| PMP | Periodo Medio de Pago |
| PMA | Periodo Medio de Almacén |
| VAN | Valor Actual Neto |
| TIR | Tasa Interna de Retorno |

---

*Lira Financial Suite · Desarrollado para Odoo 18 · © 2025*
