# Javier Ramos — entorno local Odoo 18 (fabricación)

Proyecto de Apunts/Grupadoo para el cliente **Javier Ramos, S.L.** (fabricación: taller, OFs,
barcode de planta, costes). Trabaja SIEMPRE en español y verifica con ejecuciones reales.

## Entorno local

- Compose `odoo_javierramos_local`: **Odoo 18** (imagen `odoo:18`, con `--dev=all` — recarga
  Python/XML sola al guardar) en http://localhost:8069; Postgres 16 en el 5433 del host.
- Contenedores: `odoo_javierramos_local-odoo-1` y `odoo_javierramos_local-db-1`.
- BDs: **`javierramos_prod`** (la más reciente, con todos los cambios — la de trabajo) y
  `javierramoslocal` (secundaria). Master password `odoo`. El login del admin NO es admin/admin:
  para automatizar UI, crea un usuario temporal por shell y bórralo al acabar (patrón abajo).
- Este repo (la carpeta abierta, montada como `/mnt/extra-addons`) = módulos del cliente (`apunts_jr_*`, `javier_ramos_*`, `plastec_*`, OCA) + ahora
  `grupadoo_base` y `grupadoo_formacion` (18.0.8.0.0, instalado en AMBAS BDs).
- Documentación viva, aquí en la raíz: `CAMBIOS.md` (historial) y `PENDIENTE.MD`.
- ⚠️ Preexistente: la BD tiene instalado `apunts_stock_delivery_grouped` sin carpeta en este repo
  → ERROR en cada arranque. No es de los módulos nuevos.

## Reglas

- **Nada de commits/push sin que Joan lo pida.** No pises trabajo sin commitear.
- Tras cambiar un módulo: upgrade real (`docker exec odoo_javierramos_local-odoo-1 odoo -c /etc/odoo/odoo.conf -d javierramos_prod -u <modulo> --stop-after-init --http-port=8899`),
  grep de ERROR/CRITICAL, y verificación con Playwright (instalado en el host).
- Odoo shell: `docker exec -i odoo_javierramos_local-odoo-1 odoo shell -c /etc/odoo/odoo.conf -d javierramos_prod --no-http` — ¡los cambios NO persisten sin `env.cr.commit()`!
- Pruebas de instalación: BDs desechables `test_*`; JAMÁS DROP de las dos BDs reales.
- Es Odoo **18**: `_sql_constraints` sí (models.Constraint es de 19), `group_expand` recibe
  `order`, excepciones de `odoo.exceptions`, One2many no se copian por defecto.

### Usuario temporal para automatizar la UI (borrar al acabar)
```python
u = env['res.users'].with_context(no_reset_password=True).create({
    'name': 'Prueba (temporal)', 'login': 'prueba_tmp', 'password': '<inventa-una>',
    'groups_id': [(4, env.ref('base.group_system').id)]})
env.cr.commit()
# ... y al terminar: env['res.users'].search([('login','=','prueba_tmp')]).unlink(); env.cr.commit()
```

## Los MANUALES (grupadoo_formacion) — para qué está aquí

El módulo guarda guías paso a paso con capturas anotadas; el cliente las consulta en
**Formación → Formaciones**, las valida (acta inmutable) y reporta gaps. La zona de
construcción está en **Formación → Apunts** (Guías / Gaps / Áreas / Plantillas / Importar ZIP).
Enlace público y opciones en **Ajustes → Formación**.

Flujo de fabricación de manuales (skill `/manual`):
1. **`guionista-manuales`** escribe el `.md` de cada guía en el formato del importador,
   leyendo el módulo real (menús, vistas, CAMBIOS.md) — nunca inventa pantallas.
2. **`capturista-pantallas`** navega el Odoo real con Playwright y saca las capturas
   anotadas (recuadros rojos numerados) que el guion pide.
3. Importación: carpeta plana (md + png) → `docker cp` al contenedor →
   `env['formacion.ficha'].importar_carpeta('/tmp/<carpeta>')` + `env.cr.commit()`.
4. Verificación: abrir el visor con Playwright y repasar la guía como la vería el cliente.

Convenciones de guía: público `dependiente` = personal de planta/taller, `oficina` =
administración. Pasos de UNA acción empezando por el verbo, con captura del clic exacto.
Terminología del cliente antes que jerga Odoo. Las guías quedan en `borrador`: las valida
el cliente, no nosotros.

## Referencias
- Catálogo Grupadoo: `~/Documents/Docker/odoo_comercial` (18) / `odoo_comercial_19` (19).
  El módulo de formación canónico vive allí; aquí hay una copia — si se arregla algo aquí,
  avisar para replicarlo al catálogo.
- Vault: `~/Documents/Apunts-KB` (nota del módulo en `03-Modulos/Grupadoo/grupadoo_formacion.md`,
  cliente en `02-Clientes/Javier-Ramos.md`, receta de capturas Playwright en `05-Recetas`).
