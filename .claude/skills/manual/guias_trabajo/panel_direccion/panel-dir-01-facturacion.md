---
id: panel-dir-01-facturacion
titulo: "Panel Dirección — de dónde sale: Facturación del año"
area: Panel Dirección
publico: oficina
modulo: apunts_jr_dashboard_direccion
dispositivo: ordenador
estado: borrador
alias:
  - facturado del año panel direccion
  - de donde sale la facturacion
  - cuadrar facturacion anual
---

## Cuándo se usa
Para entender y demostrar de dónde sale el número **"Facturación del año"** del Panel Dirección.
Es lo que se ha **facturado a clientes** desde el 1 de enero, **sin IVA** (las facturas menos los
abonos). Ejemplo con los datos de hoy: **812.555,09 €**.

## Antes de empezar
- Necesitas permiso de contabilidad (solo lectura) para ver el menú **Dirección**.

## Pasos
1. Abre **Dirección → Panel Dirección**.
   ![Panel Dirección, tarjeta 1 recuadrada](panel-dir-01-facturacion-01-panel.png)
2. Mira la tarjeta **1 · Facturación del año** y fíjate en el número (aquí 812.555,09 €).
   ![Tarjeta Facturación del año de cerca](panel-dir-01-facturacion-02-tarjeta.png)
3. Ese número sale de las **facturas de cliente**. Ve a **Contabilidad → Clientes → Facturas**.
   ![Menú Contabilidad, Clientes, Facturas](panel-dir-01-facturacion-03-menu.png)
4. Aplica el filtro **Este año** y deja solo las **Publicadas** (contabilizadas).
   ![Filtro Este año y estado Publicado](panel-dir-01-facturacion-04-filtro.png)
5. Abajo del todo, en la columna de **base imponible** (sin IVA), mira el **total**: coincide con
   el número de la tarjeta.
   ![Total de base imponible que cuadra con la tarjeta](panel-dir-01-facturacion-05-total.png)
6. **Cómo se calcula:** se suman las bases imponibles (sin IVA) de todas las facturas de cliente
   publicadas del año, y **se restan los abonos** (facturas rectificativas). Hoy son 377
   documentos que suman 812.555,09 €.

## Si algo va mal
- El número no cuadra con el listado: comprueba que en el listado tienes el filtro **Este año** y
  **solo Publicadas**; los borradores no cuentan.

## Escalar
Si el total del panel y el del listado no coinciden aun con los mismos filtros, avisa a Apunts con
una captura de los dos.
