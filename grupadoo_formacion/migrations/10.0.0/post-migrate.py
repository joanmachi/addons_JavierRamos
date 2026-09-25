# -*- coding: utf-8 -*-
"""v10.0.0 — al ACTUALIZAR el módulo:
- candado de la zona Apunts a 'apunts' si estaba vacío (los clientes instalados con
  v2..v9 lo tenían vacío = puerta abierta);
- las etiquetas del público pasan a ser configurables: no se toca nada aquí (vacío =
  por defecto 🛒 Tienda / 🗂️ Oficina). En Javier Ramos hay que poner 🏭 Planta en Ajustes.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env['ir.config_parameter'].sudo()
    if not (icp.get_param('grupadoo_formacion.clave_acceso') or '').strip():
        icp.set_param('grupadoo_formacion.clave_acceso', 'apunts')
