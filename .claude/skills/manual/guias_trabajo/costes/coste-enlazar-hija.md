---
id: coste-enlazar-hija
titulo: "Enlazar una OF hija que se lanzó suelta"
area: "Costes y márgenes"
publico: oficina
modulo: apunts_jr_wip_costes_of
dispositivo: ordenador
estado: borrador
alias:
  - hija suelta que no suma a la madre
  - decir de qué OF es hija una orden
  - vincular subconjunto a su conjunto
  - OF madre de una hija
---

## Cuándo se usa
Un subconjunto se fabricó en una OF que se lanzó por separado (no salió del conjunto) y por eso su coste no sube a la OF madre. Le indicas a mano cuál es su madre.

## Antes de empezar
Abre la **OF hija** (la que fabrica el componente) y ten a mano el número de la **OF madre**.

## Pasos
1. En la OF hija, abre la pestaña **Varios**.
   ![](coste-enlazar-hija-01.png)
2. Busca el campo **OF madre (si es una hija suelta)** y selecciona la orden madre.
   ![](coste-enlazar-hija-02.png)
3. Guarda los cambios.
   ![](coste-enlazar-hija-03.png)
4. Abre la OF madre: el coste de la hija ya sube al componente correspondiente (pestaña Material de su COSTE OF) y la hija aparece en el smart button **Orden de fabricación hija**.

## Si algo va mal
- No encuentras el campo: asegúrate de estar en la pestaña **Varios** de la OF hija (no en la madre).
- No aparece la madre al buscar: escribe su número de OF; el campo solo deja elegir órdenes existentes.
- Enlazaste la hija equivocada: vacía el campo **OF madre (si es una hija suelta)** y vuelve a seleccionar la correcta.

## Escalar
Si tras enlazar la hija su coste no aparece en la madre, avisa a la oficina técnica con los números de la OF madre y la hija.
