---
id: panel-dir-03-cartera
titulo: "Panel Dirección — de dónde sale: Cartera pendiente"
area: Panel Dirección
publico: oficina
modulo: apunts_jr_dashboard_direccion
dispositivo: ordenador
estado: borrador
alias:
  - cartera pendiente panel
  - vendido no entregado
  - pedidos pendientes de entrega
---

## Cuándo se usa
Para saber de dónde sale **"Cartera pendiente"**: lo ya **vendido pero aún no entregado** (trabajo
comprometido que todavía no ha salido). Ejemplo de hoy: **185.956,40 €**.

## Antes de empezar
- Acceso al tablero **Pedidos pendientes de entrega**.

## Pasos
1. Abre **Dirección → Panel Dirección** y localiza la tarjeta **3 · Cartera pendiente**.
   ![Panel con la tarjeta Cartera pendiente recuadrada](panel-dir-03-cartera-01-panel.png)
2. Ese número es el **valor pendiente** del tablero de entregas. Abre **Pedidos pendientes de
   entrega** y pulsa **Actualizar**.
   ![Tablero Pedidos pendientes de entrega](panel-dir-03-cartera-02-tablero.png)
3. Mira el indicador **Valor pendiente**: coincide con la tarjeta.
   ![Valor pendiente que cuadra con la tarjeta](panel-dir-03-cartera-03-valor.png)
4. Para ver el detalle, pulsa **Ver tabla**: cada línea es un pedido con unidades sin servir.
   ![Lista de líneas pendientes de entrega](panel-dir-03-cartera-04-tabla.png)
5. **Cómo se calcula:** por cada línea de pedido confirmada se toma **lo que falta por entregar**
   (vendido − entregado) y se multiplica por su **precio**; se suman todas. Es dinero vendido que
   aún está por fabricar/servir.

## Si algo va mal
- Cambia respecto a ayer: es normal, baja según se entregan pedidos y sube con pedidos nuevos.

## Escalar
Si el valor del tablero y el del panel no coinciden tras Actualizar, avisa a Apunts.
