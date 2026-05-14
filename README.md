# Odoo 18 Enterprise - Javier Ramos | Módulos Custom

## Contexto del proyecto

Este repositorio contiene los módulos custom y de terceros del cliente **Javier Ramos** sobre **Odoo 18 Enterprise**. El entorno de desarrollo es un Docker local que replica la base de datos de producción (servidor Plesk: `apuntserp.es`).

Hay **dos desarrolladores trabajando en paralelo** sobre esta misma carpeta. Cada uno tiene su propio entorno Docker local. El flujo de trabajo es:
- Cada desarrollador trabaja en su rama o directamente en `main`
- Cada modificación se commitea por separado con el prefijo `[NNN]` que corresponde a la entrada en `CAMBIOS.md`
- Al finalizar, se comparten los commits y se decide qué fusionar

---

## Instrucciones para Claude Code

### Lo que eres y lo que haces aquí

Eres el asistente de desarrollo de este proyecto Odoo. Tu trabajo es ayudar a programar modificaciones sobre los módulos custom del cliente. **Todas las modificaciones que hagas deben seguir el flujo de trabajo descrito abajo.**

### Estructura de carpetas relevante

```
addons/                          ← estás aquí (este repo git)
├── javier_ramos_pedidos/        ← módulo principal de facturas, pedidos, albaranes
├── javier_ramos_taller/         ← módulo de taller/producción
├── javier_ramos_taller_simple/  ← variante simplificada del taller
├── plastec_pedido/              ← módulo específico Plastec
├── plastec_taller/              ← taller Plastec
├── lira_dashboard_contabilidad/ ← dashboard contabilidad
├── apunts_*/                    ← módulos de Apunts Informàtica
└── ...otros módulos de terceros
```

Los módulos a tocar habitualmente son los que empiezan por `javier_ramos_`, `plastec_` y `lira_`.

### Entorno Docker local

El entorno corre con Docker Compose. Los contenedores son:
- `odoo_javierramos_local-odoo-1` — Odoo 18 en `http://localhost:8069`
- `odoo_javierramos_local-db-1` — PostgreSQL 16 en `localhost:5433`

Base de datos local: `javierramoslocal`  
Usuario Odoo: `direccion@jramos.com`  
Contraseña Odoo: `admin123`

### Cómo aplicar cambios en Odoo

Cada vez que modifiques vistas XML o modelos Python de un módulo, aplica así:

```bash
docker exec odoo_javierramos_local-odoo-1 odoo -d javierramoslocal --update=NOMBRE_MODULO --stop-after-init
docker restart odoo_javierramos_local-odoo-1
```

---

## Flujo de trabajo obligatorio para cada modificación

### 1. Haz el cambio en el código

Edita los ficheros necesarios dentro de `addons/`.

### 2. Añade la entrada en CAMBIOS.md

Abre `CAMBIOS.md` y añade una nueva sección siguiendo el formato:

```markdown
## [NNN] Título corto del cambio

**Fecha:** YYYY-MM-DD
**Módulo:** `nombre_modulo`
**Ficheros modificados:**
- `ruta/al/fichero.py` — descripción de qué hace
- `ruta/al/fichero.xml` — descripción de qué hace

**Vista/función afectada:** dónde se ve en Odoo

**Qué hace:**
Descripción clara del cambio.

**Para aplicar cambios:**
\```
docker exec odoo_javierramos_local-odoo-1 odoo -d javierramoslocal --update=MODULO --stop-after-init
docker restart odoo_javierramos_local-odoo-1
\```

---
```

El número `[NNN]` es correlativo al último que haya en `CAMBIOS.md`.

### 3. Commitea los cambios

```bash
git add <ficheros modificados> CAMBIOS.md
git commit -m "[NNN] Título corto del cambio"
```

El mensaje del commit debe coincidir con el título de la entrada en `CAMBIOS.md`.

---

## Cómo recibir los cambios de otro desarrollador (sin perder los tuyos)

Esta sección explica paso a paso cómo un compañero puede integrar los commits de esta rama con sus propios cambios locales.

---

### Situación de partida

Este repositorio tiene los siguientes commits nuevos desde el estado inicial:

```
0f6d001  Supervisor planta: Click en fila, abre OF
9f28a91  Anotacion de cambios
a0738fa  Albaranes de entrega, valorados y no valorados
79bdac6  Columna fecha vencimiento en facturas
5505730  Añadir README.md con instrucciones para Claude Code y CAMBIOS.md
ee32548  Estado inicial - modulos extraidos de produccion Javier Ramos
```

Los módulos modificados son: `javier_ramos_pedidos`, `stock_picking_report_valued`, `apunts_stock_delivery_grouped` y `lira_mfg_supervisor`. Consulta `CAMBIOS.md` para el detalle completo de cada cambio.

---

### Paso 1 — Guarda tu trabajo antes de nada

Comprueba si tienes cambios sin commitear:

```bash
git status
```

**Si tienes cambios sin commitear**, guárdalos temporalmente:

```bash
git stash push -m "mis cambios pendientes"
```

**Si ya tienes commits propios en tu rama**, anótalos (verás sus hashes con `git log --oneline`). No hace falta hacer nada todavía.

---

### Paso 2 — Obtén los commits nuevos

**Opción A — Si ya tienes el repositorio clonado:**

```bash
git fetch origin
git log origin/main --oneline   # revisa qué commits nuevos hay
```

**Opción B — Si no tienes el repositorio:**

```bash
git clone <URL_DEL_REPO> addons
cd addons
```

---

### Paso 3 — Integra los cambios nuevos con los tuyos

Aquí hay dos casos:

#### Caso 1: Tus cambios están en commits propios

Usa `rebase` para poner tus commits encima de los nuevos (lo más limpio):

```bash
git rebase origin/main
```

Si hay conflictos en algún fichero, Git te lo indicará. Resuélvelos así:

```bash
# 1. Abre el fichero en conflicto, busca los marcadores <<<<<<< HEAD
#    y edita hasta que quede como quieras

# 2. Marca el conflicto como resuelto
git add <fichero_en_conflicto>

# 3. Continúa el rebase
git rebase --continue
```

Si en algún momento quieres cancelar y volver al estado anterior:
```bash
git rebase --abort
```

#### Caso 2: Tus cambios están en el stash (sin commitear)

```bash
# Primero sube a la punta de origin/main
git merge origin/main

# Luego recupera tus cambios
git stash pop
```

Si `stash pop` produce conflictos, resuelve igual que arriba (busca `<<<<<<<` en los ficheros afectados, edita, `git add`, y ya está).

---

### Paso 4 — Comprueba qué módulos hay que actualizar en Odoo

Mira qué ficheros cambiaron respecto al estado que tenías:

```bash
git diff HEAD~5 --name-only   # ajusta el número según los commits nuevos
```

Los módulos afectados por los commits nuevos son:

| Módulo | Tipo de cambio |
|---|---|
| `javier_ramos_pedidos` | Campo Python + vista XML |
| `stock_picking_report_valued` | Modelo Python + XML reporte |
| `apunts_stock_delivery_grouped` | XML reporte |
| `lira_mfg_supervisor` | Modelo Python + vistas XML + JS |

Actualiza solo los que hayas integrado (o todos para ir seguro):

```bash
docker exec odoo_javierramos_local-odoo-1 odoo -d javierramoslocal \
  --update=javier_ramos_pedidos,stock_picking_report_valued,apunts_stock_delivery_grouped,lira_mfg_supervisor \
  --stop-after-init

docker restart odoo_javierramos_local-odoo-1
```

Para `lira_mfg_supervisor` (cambio JS), además de actualizar el módulo, recarga la página con **Ctrl+Shift+R** en el navegador para forzar la recarga de assets.

---

### Paso 5 — Verifica que todo funciona

Comprueba en Odoo los puntos clave de cada cambio integrado:

- **Facturas (Contabilidad > Clientes > Facturas)**: debe aparecer la columna "Fecha Venc." como columna opcional.
- **Albarán (cualquier traslado > Imprimir)**: deben aparecer dos opciones: el albarán estándar y "Imprimir Albarán Valorado".
- **Albarán PDF**: la tabla de productos no debe aparecer duplicada.
- **Supervisor Planta**: al hacer clic en una fila, debe abrir la orden de fabricación correspondiente.

---

### Resolución de conflictos frecuentes

**Conflicto en `CAMBIOS.md`:**  
Es muy probable porque ambos desarrolladores añaden entradas. Abre el fichero, mantén TODAS las entradas de ambos lados (las tuyas y las nuevas) ordenadas por número `[NNN]`, y ajusta la numeración si es necesario.

**Conflicto en un fichero XML de vistas:**  
Lee los dos bloques en conflicto y decide si deben convivir (normalmente sí — son `<record>` independientes) o si uno reemplaza al otro. Cuando tengas dudas, consulta `CAMBIOS.md` para entender qué hace cada bloque.

**Conflicto en un fichero Python de modelo:**  
Normalmente son métodos o campos distintos que se pueden mantener juntos. Si los dos lados tocan el mismo método, hay que leerlos con cuidado y fusionar la lógica manualmente.

---

## Notas técnicas importantes

- **Odoo 18**: las vistas XML usan xpath. Antes de escribir un xpath, verifica qué campos existen en la vista padre mirando el fuente dentro del contenedor en `/usr/lib/python3/dist-packages/odoo/addons/`.
- **Enterprise**: la carpeta `enterprise/` está en el nivel superior (fuera de este repo). No la toques.
- **Line endings**: este repo usa LF (`.gitattributes` configurado). No cambies esa configuración.
- **`__pycache__`**: ignorado por `.gitignore`. No los commitees.
- **La vista lista de facturas** en Odoo 18 es `account.view_invoice_tree`, no `account.view_move_tree`.
