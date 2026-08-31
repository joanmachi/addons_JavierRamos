---
id: panel-dir-09-horas
titulo: "Panel Dirección — de dónde sale: Horas productivas"
area: Panel Dirección
publico: oficina
modulo: apunts_jr_dashboard_direccion
dispositivo: ordenador
estado: borrador
alias:
  - horas productivas panel
  - jornada cumplida operarios
  - porcentaje de cumplimiento de jornada
---

## Cuándo se usa
Para saber de dónde sale **"Horas productivas (mes)"**: cuánto **cumplen la jornada** los operarios
—horas de presencia y ausencias justificadas frente a las horas de calendario—. Ejemplo de hoy:
**62,1 %**.

## Antes de empezar
- Acceso a **Gestión Taller**.

## Pasos
1. Abre **Dirección → Panel Dirección** y localiza la tarjeta **9 · Horas productivas (mes)**.
   ![Panel con la tarjeta Horas productivas recuadrada](panel-dir-09-horas-01-panel.png)
2. El dato sale del taller. Abre **Gestión Taller → KPIs de fichaje** y pon el rango del **mes**;
   pulsa **Actualizar**.
   ![KPIs de fichaje del mes](panel-dir-09-horas-02-kpis.png)
3. Fíjate en el indicador **Jornada cumplida**: es el mismo porcentaje que la tarjeta.
   ![Indicador Jornada cumplida](panel-dir-09-horas-03-jornada.png)
4. **Cómo se calcula:** **% = (horas de presencia + ausencias aprobadas) ÷ horas de calendario**
   (días laborables L–V × horas por día). Si un operario estuvo o tuvo permiso justificado, cuenta;
   si faltó sin justificar, baja el porcentaje.

## Si algo va mal
- El porcentaje baja de golpe: suele ser por ausencias aún **sin aprobar** o fichajes sin cerrar de
  ese mes; en cuanto se regularizan, sube.

## Escalar
Si el porcentaje del panel y el de KPIs de fichaje no coinciden con el mismo mes, avisa a Apunts.
