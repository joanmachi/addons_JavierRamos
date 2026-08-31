---
id: panel-dir-06-cobros
titulo: "Panel Dirección — de dónde sale: Cobros pendientes"
area: Panel Dirección
publico: oficina
modulo: apunts_jr_dashboard_direccion
dispositivo: ordenador
estado: borrador
alias:
  - cobros pendientes panel
  - facturas sin cobrar
  - lo que nos deben los clientes
---

## Cuándo se usa
Para saber de dónde sale **"Cobros pendientes"**: las facturas de cliente **emitidas y todavía sin
cobrar** (lo que nos deben). Ejemplo de hoy: **301.738,57 €**.

## Antes de empezar
- Permiso de contabilidad.

## Pasos
1. Abre **Dirección → Panel Dirección** y localiza la tarjeta **6 · Cobros pendientes**.
   ![Panel con la tarjeta Cobros pendientes recuadrada](panel-dir-06-cobros-01-panel.png)
2. Ve a **Contabilidad → Clientes → Facturas**.
   ![Menú Contabilidad, Clientes, Facturas](panel-dir-06-cobros-02-menu.png)
3. Aplica los filtros **Por pagar** y **Publicado** (así excluyes borradores): quedan solo las facturas contabilizadas que aún deben cobrarse.
   ![Filtro facturas sin pagar](panel-dir-06-cobros-03-filtro.png)
4. Mira la columna **Importe adeudado** (lo que queda por cobrar) y su **total**: coincide con la
   tarjeta.
   ![Total del importe adeudado](panel-dir-06-cobros-04-total.png)
5. **Cómo se calcula:** se suma el **importe adeudado** (lo que falta por cobrar, no el total de
   la factura) de todas las facturas de cliente en estado **por pagar** o **pago parcial** y **publicadas**. Hoy
   son 85 facturas que suman 301.738,57 €.

## Si algo va mal
- Sale de más: recuerda que es el **adeudado**, no el total; una factura cobrada a medias solo
  cuenta lo que falta.

## Escalar
Si no cuadra con el listado filtrado, avisa a Apunts con captura.
