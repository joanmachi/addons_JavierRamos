# Odoo 18 Enterprise - Javier Ramos | Módulos Custom

## Contexto del proyecto

Este repositorio contiene los módulos custom y de terceros del cliente **Javier Ramos** sobre **Odoo 18 Enterprise**. El entorno de desarrollo es un Docker local que replica la base de datos de producción (servidor Plesk: `apuntserp.es`).

Hay **dos desarrolladores trabajando en paralelo**: **Joan** y **Alex**. Cada uno tiene su propio entorno Docker local.

**Repositorio GitHub:** `https://github.com/joanmachi/addons_JavierRamos.git`

---

## Entorno Docker local

| | |
|---|---|
| **Odoo** | `http://localhost:8069` |
| **Contenedor Odoo** | `odoo_javierramos_local-odoo-1` |
| **Contenedor DB** | `odoo_javierramos_local-db-1` |
| **Base de datos** | `javierramoslocal` |
| **Usuario Odoo** | `direccion@jramos.com` |
| **Contraseña Odoo** | `admin123` |

---

## Cómo aplicar cambios en Odoo

Después de modificar vistas XML o modelos Python:

```bash
# Parar Odoo
cd C:\Users\<tu_usuario>\Documents\Docker\odoo_18_JavierRamos
docker compose stop odoo

# Actualizar módulo(s)
docker compose run --rm odoo odoo -d javierramoslocal --update NOMBRE_MODULO --stop-after-init

# Volver a arrancar
docker compose start odoo
```

Para instalar un módulo nuevo (que no estaba instalado):
```bash
docker compose run --rm odoo odoo -d javierramoslocal --init NOMBRE_MODULO --stop-after-init
```

Para limpiar la caché de assets JS/CSS (cuando cambias ficheros .js o .css):
```bash
docker exec odoo_javierramos_local-db-1 psql -U odoo -d javierramoslocal -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"
```

---

## Flujo de trabajo

Cada modificación sigue este patrón:

1. Editar los ficheros del módulo
2. Actualizar el módulo en Odoo y verificar que funciona
3. Commitear: `git commit -m "[NNN] Descripción corta"`
4. Subir: `git push origin main` (o tu rama)

---

## Estado actual de los módulos custom

### Módulos modificados por Joan (sobre la base de Alex)

| Módulo | Cambios |
|---|---|
| `javier_ramos_pedidos` | Campo `invoice_due_date_display` en `account.move`; columna "Fecha Venc." en lista facturas |
| `javier_ramos_taller_simple` | Etiqueta albarán rediseñada (logo, barcodes, formato 105×150mm); xpath Studio comentado |
| `lira_mfg_supervisor` | Click en fila del panel abre la orden de fabricación (OWL component + método Python) |

### Módulos que existen pero no se han tocado en este repo
- `apunts_barcode_workorder`, `apunts_jr_gestion_taller`, `apunts_jr_wip_costes_of`
- `lira_dashboard_contabilidad`, `apunts_jr_parciales_of` (nuevo, instalado)
- `javier_ramos_pedidos`, `plastec_*`, `lira_*`

### Módulos eliminados por Alex (ya no están en el repo)
- `apunts_stock_delivery_grouped` — eliminado, si estaba instalado en Odoo puede dar warning
- `apunts_wip` — eliminado

---

## Instrucciones para Claude Code

> Esta sección la lee Claude (la IA) para entender el proyecto desde cero.

### Qué eres y qué haces aquí

Eres el asistente de desarrollo de este proyecto Odoo 18 Enterprise para el cliente Javier Ramos. Tu trabajo es implementar modificaciones sobre los módulos custom. **Antes de tocar nada, lee los ficheros relevantes con Read.**

### Reglas importantes

- **Nunca comentes un `xpath` sin entender por qué falla.** Si un xpath falla, primero verifica si el campo padre existe en la vista heredada ejecutando un grep en `/usr/lib/python3/dist-packages/odoo/addons/` dentro del contenedor.
- **El campo logo en Odoo 18 es `logo_web`**, no `logo` (`res.company.logo_web`).
- **Para abrir un formulario desde JS en Odoo 18**, el action dict debe incluir `'views': [(False, 'form')]` o el frontend lanza `Cannot read properties of undefined (reading 'map')`.
- **Las etiquetas PDF** usan `web.html_container` (no `web.internal_layout`) y necesitan `class="page article"` en el div de página para que `_prepare_html` añada el charset y el zoom no sea 0.47 por culpa de dpi=203.
- **Después de cambiar JS/CSS**, borrar la caché de assets en la BD y reiniciar Odoo.
- **Xpath `x_studio_rdenes_de_fabricacin`** en `javier_ramos_taller_simple/views/pedidos.xml` está **comentado** a propósito — el campo Studio fue eliminado de la vista padre en producción. No lo reactives.

### Estructura clave de ficheros

```
addons/
├── javier_ramos_pedidos/
│   ├── models/
│   │   ├── __init__.py             ← importa account_move, sale_order, etc.
│   │   ├── account_move.py         ← hereda account.move, añade invoice_due_date_display
│   │   └── ...
│   └── views/
│       └── factura.xml             ← vista lista facturas con columna fecha vencimiento
├── javier_ramos_taller_simple/
│   ├── report/
│   │   ├── labels.xml              ← etiqueta albarán (WHOUT/WHIN), diseño propio
│   │   └── paper_format.xml        ← 105×150mm, dpi=96 (importante: NO poner dpi=203)
│   └── views/
│       └── pedidos.xml             ← xpath Studio comentado
└── lira_mfg_supervisor/
    ├── models/
    │   └── lira_supervisor_workorder.py  ← action_open_production() al final
    ├── views/
    │   └── lira_supervisor_views.xml     ← js_class="lira_supervisor_list" en ambas listas
    ├── static/src/js/
    │   └── supervisor_list.js            ← OWL component, openRecord → action_open_production
    └── __manifest__.py                   ← supervisor_list.js en web.assets_backend
```

---

## Para Alex: cómo recibir los cambios de Joan

### Paso 1 — Obtén el repositorio

**Si aún no tienes el repo clonado:**
```bash
git clone https://github.com/joanmachi/addons_JavierRamos.git addons
cd addons
```

**Si ya lo tienes clonado:**
```bash
git fetch origin
git log origin/main --oneline   # revisa los commits nuevos
```

### Paso 2 — Guarda tu trabajo actual

```bash
git status
```

- Si tienes cambios sin commitear: `git stash push -m "mis cambios"`
- Si tienes commits propios en tu rama: anota el hash del último con `git log --oneline`

### Paso 3 — Integra

**Si trabajas en `main`:**
```bash
git merge origin/main
```

**Si trabajas en tu propia rama:**
```bash
git rebase origin/main
```

Si hay conflictos en `CAMBIOS.md`: mantén las entradas de los dos lados, reordénalas por número `[NNN]`.
Si hay conflictos en XML: los `<record>` suelen ser independientes, normalmente puedes conservar ambos.

### Paso 4 — Actualiza los módulos en Odoo

Los módulos que Joan ha modificado son:

```bash
cd C:\ruta\a\tu\Docker\odoo_18_JavierRamos
docker compose stop odoo
docker compose run --rm odoo odoo -d javierramoslocal \
  --update javier_ramos_pedidos,javier_ramos_taller_simple,lira_mfg_supervisor \
  --stop-after-init
docker compose start odoo
```

Limpia también la caché de assets (por el cambio JS en lira_mfg_supervisor):
```bash
docker exec odoo_javierramos_local-db-1 psql -U odoo -d javierramoslocal \
  -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"
```

### Paso 5 — Verifica

- **Facturas** → debe aparecer la columna "Fecha Venc." (opcional, hay que activarla desde el icono de columnas)
- **Etiqueta albarán** → al imprimir un albarán de salida (WHOUT), debe salir con logo arriba, recuadro oscuro, barcodes de artículo y orden
- **Panel Supervisor Planta** → al hacer clic en una fila, debe abrir la orden de fabricación

---

## Prompt para darle a tu Claude

Copia esto y pégaselo a tu Claude Code al inicio de la sesión:

```
Estás trabajando en el proyecto Odoo 18 Enterprise del cliente Javier Ramos.
Lee el fichero README.md en la raíz del repositorio de addons — contiene todo el
contexto del proyecto, las reglas técnicas importantes y el estado actual de los módulos.

El repositorio está en: C:\Users\<TU_USUARIO>\Documents\Docker\odoo_18_JavierRamos\addons

Antes de hacer cualquier cambio:
1. Lee README.md completo
2. Lee el fichero que vayas a modificar
3. Verifica que el xpath o campo que vayas a usar existe en la vista/modelo padre

El compañero Joan ya ha hecho una serie de modificaciones — están documentadas en
CAMBIOS.md y en la sección "Estado actual" del README. No las repitas ni las sobreescribas.
```

---

## Notas técnicas

- **Odoo 18**: usa `<list>` en lugar de `<tree>` en las vistas
- **Enterprise**: la carpeta `enterprise/` está en el nivel superior (fuera de este repo). No la toques
- **Line endings**: este repo usa LF
- **`__pycache__`**: ignorado por `.gitignore`
- **Vista lista de facturas** en Odoo 18: `account.view_invoice_tree`
