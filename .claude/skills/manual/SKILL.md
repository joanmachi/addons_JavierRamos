# Fabricar manuales de formación (grupadoo_formacion) para Javier Ramos

Pipeline completo: guion → capturas reales anotadas → importación → verificación en el visor.
Uso: `/manual <tema o módulo>` (p. ej. `/manual cerrar OFs` o `/manual apunts_taller_control`).
Sin argumentos: propone temas leyendo `CAMBIOS.md` y `PENDIENTE.MD` y pregunta.

## 1. Guion

- Crea la carpeta de trabajo `guias_trabajo/<tema>/` aquí (queda sin trackear; no la commitees).
- Lanza `guionista-manuales` con el tema, el módulo implicado y la carpeta. Devuelve los `.md`
  (formato del importador) + `CAPTURAS.md` con la lista de capturas y qué marcar en rojo.
- Revisa sus dudas: si el guion no pudo aclarar una pantalla, resuélvelo TÚ mirando el código
  antes de seguir (no pases dudas al capturista).

## 2. Capturas

- Lanza `capturista-pantallas` con la carpeta y el `CAPTURAS.md`. Trabaja sobre la BD
  `javierramos_prod` en http://localhost:8069.
- Si reporta pantallas que no cuadran con el guion, vuelve al guionista (una ronda) con lo
  observado — la captura manda: el manual describe lo que SE VE.

## 3. Importar

- Carpeta plana (los .md y .png juntos) al contenedor y dentro:
```bash
docker cp guias_trabajo/<tema>/. odoo_javierramos_local-odoo-1:/tmp/guias_<tema>/
docker exec -i odoo_javierramos_local-odoo-1 odoo shell -c /etc/odoo/odoo.conf -d javierramos_prod --no-http <<'EOF'
res = env['formacion.ficha'].importar_carpeta('/tmp/guias_<tema>')
print(res)
env.cr.commit()   # ¡sin commit no persiste!
EOF
```
- `res['avisos']` debe quedar vacío (capturas que faltan = volver al paso 2).
- Reimportar es seguro: mismo `id` = actualiza (sustituye pasos e imágenes).

## 4. Verificar como el cliente

- Playwright: entra al visor (Formación → Formaciones), busca la guía por un alias, ábrela y
  recórrela paso a paso; captura de la portada y de un paso con imagen para el informe.
  (Usuario temporal por shell; bórralo al acabar — patrón en CLAUDE.md.)
- Comprueba que el texto usa la terminología del cliente y que las capturas casan con los pasos.

## 5. Informe

- Guías creadas (id, título, área, pasos, capturas), avisos del importador, datos
  DEMO-FORMACION creados, y qué falta para que el cliente las valide.
- Las guías quedan en **borrador** a propósito: las valida el cliente desde el visor o el
  enlace público (Ajustes → Formación). No las valides tú.
- No borres `guias_trabajo/<tema>/` — es la fuente reexportable (y el ZIP para llevar la guía
  a otro cliente sale gratis con "Exportar ZIP").
