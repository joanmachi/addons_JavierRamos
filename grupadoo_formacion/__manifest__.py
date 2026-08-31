# -*- coding: utf-8 -*-
{'name': 'Asistente de Formación',
 'version': '18.0.8.1.0',
 'category': 'Services',
 'summary': 'Guías paso a paso del Odoo del cliente, con capturas anotadas, validaciones '
            'con acta, gaps con tablero de seguimiento, enlace público sin usuario y '
            'tickets de asistencia hacia el helpdesk de Grupadoo al cerrar el proyecto.',
 'author': 'GRUPADOO',
 'website': 'https://www.grupadoo.com/',
 'license': 'LGPL-3',
 'depends': ['web', 'mail', 'grupadoo_base'],
 'data': ['security/formacion_security.xml',
          'security/ir.model.access.csv',
          'data/formacion_data.xml',
          'data/formacion_plantillas.xml',
          'views/formacion_views.xml',
          'views/publico_templates.xml',
          'views/res_config_settings_views.xml'],
 'assets': {'web.assets_backend': [
     'grupadoo_formacion/static/src/visor/visor.scss',
     'grupadoo_formacion/static/src/visor/visor.js',
     'grupadoo_formacion/static/src/visor/visor.xml',
 ]},
 'post_init_hook': 'post_init_hook',
 'application': True,
 'installable': True,
 'description': """
Asistente de Formación
======================

¿Qué hace?
----------
Guarda las guías de formación del Odoo del cliente (paso a paso, con captura en
cada paso) y las sirve en un asistente visual para el personal de tienda u
oficina, con buscador por cómo lo diría el usuario ("hacer un ticket", "cobrar").
El cliente valida cada guía (acta inmutable con nombre y fecha) y avisa de los
gaps — lo que no cuadra con su Odoo real — con tablero de seguimiento.

¿Para qué sirve?
----------------
Para que el personal aprenda y resuelva dudas solo, sin llamar al encargado, y
para que la consultora tenga la prueba de qué formación se entregó y se aceptó:
validaciones con acta, gaps con respuesta y horas de desarrollo por guía.

Cómo se usa
-----------
Añade la aplicación **Formación** con estos menús:

1. **Formación → Formaciones**: el asistente visual para el cliente — busca una
   guía (sin acentos también) o entra por área y sigue los pasos uno a uno, con
   atajos de teclado (←/→, Enter, Esc). Desde ahí valida, avisa o comenta.
2. **Formación → Desarrollos**: los gaps en solo lectura, para consultar en qué
   está cada aviso.
3. **Formación → Apunts** (solo equipo constructor, con clave de sesión):
   **Guías** (tablero y edición), **Gaps** (gestión y respuesta), **Áreas**,
   **Plantillas** (guías esqueleto para arrancar rápido) e **Importar guías
   (ZIP)** — sube los .md con sus imágenes sin tocar la consola.
4. **Ajustes → Formación**: "solo guías validadas", tablero de avisos, el
   enlace público para compartir con el cliente sin usuario de Odoo y el
   **Soporte Grupadoo post-proyecto**.
5. **Al cerrar el proyecto**: enciende "Soporte Grupadoo" en Ajustes y aparece
   "🛟 Necesito asistencia" en el visor y en el enlace público: el cliente abre
   la incidencia desde la propia guía y el ticket llega por correo al helpdesk
   de Grupadoo señalando el área, la guía, el paso y el módulo de la pantalla.

Qué incluye
-----------
* Guías con pasos numerados automáticamente, capturas e imágenes de sección.
* Flujo borrador → en validación → validado con actas inmutables.
* Gaps del cliente con respuesta obligatoria y tablero público de seguimiento.
* Plantillas, duplicado seguro, importación ZIP y exportación ZIP (ida y vuelta).
* Enlace público con token regenerable y visor OWL con buscador con ranking.

Nota técnica
------------
Modelos ``formacion.ficha``, ``formacion.paso``, ``formacion.area``,
``formacion.gap``, ``formacion.validacion``. El visor es una client action OWL
con scope propio ``.ff`` (réplica de la estética del asistente web original,
misma familia de morados que la marca). Depende de: web, grupadoo_base.

---

Desarrollado por Grupadoo — https://www.grupadoo.com/
"""}
