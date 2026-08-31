# -*- coding: utf-8 -*-
{'name': 'Base de Diseño',
 'version': '18.0.1.0.0',
 'category': 'Technical',
 'summary': 'Sistema de diseño común (color e imagen de marca) que comparten todos los módulos '
            'Grupadoo.',
 'author': 'GRUPADOO',
 'website': 'https://www.grupadoo.com/',
 'license': 'LGPL-3',
 'depends': ['web'],
 'assets': {'web.assets_backend': ['grupadoo_base/static/src/scss/grupadoo_design.scss']},
 'installable': True,
 'description': """
Base de Diseño
==============

¿Qué hace?
----------
Aporta el sistema de diseño común (colores e imagen de marca) que comparten
todos los módulos Grupadoo, para que se vean uniformes dentro de Odoo.

¿Para qué sirve?
----------------
Centraliza los estilos en un único sitio: en vez de repetir colores y detalles
visuales en cada módulo, todos beben de esta base. Así la imagen es coherente y
cualquier ajuste de estilo se hace una sola vez.

Cómo se usa
-----------
No añade menús ni pantallas: actúa por detrás cargando sus estilos en toda la
interfaz de Odoo.

1. Se instala como dependencia de los demás módulos Grupadoo.
2. Sus estilos se aplican automáticamente al escritorio de Odoo.
3. No requiere ninguna configuración por parte del usuario.

Qué incluye
-----------
* Hoja de estilos de marca compartida (``grupadoo_design.scss``).
* Colores e imagen comunes para todos los módulos Grupadoo.
* Base sobre la que se apoyan el resto de módulos.

Nota técnica
------------
Módulo técnico sin modelos ni vistas; solo carga un ``scss`` en
``web.assets_backend``. Depende de: web.

---

Desarrollado por Grupadoo — https://www.grupadoo.com/
"""}
