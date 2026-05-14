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

## Notas técnicas importantes

- **Odoo 18**: las vistas XML usan xpath. Antes de escribir un xpath, verifica qué campos existen en la vista padre mirando el fuente dentro del contenedor en `/usr/lib/python3/dist-packages/odoo/addons/`.
- **Enterprise**: la carpeta `enterprise/` está en el nivel superior (fuera de este repo). No la toques.
- **Line endings**: este repo usa LF (`.gitattributes` configurado). No cambies esa configuración.
- **`__pycache__`**: ignorado por `.gitignore`. No los commitees.
- **La vista lista de facturas** en Odoo 18 es `account.view_invoice_tree`, no `account.view_move_tree`.
