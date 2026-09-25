# -*- coding: utf-8 -*-
from . import controllers
from . import models


def post_init_hook(env):
    # genera el token del enlace público si no existe
    env['formacion.ficha']._token_publico()
    # candado de la zona Apunts: 'apunts' si nadie ha puesto otra cosa
    icp = env['ir.config_parameter'].sudo()
    if not (icp.get_param('grupadoo_formacion.clave_acceso') or '').strip():
        icp.set_param('grupadoo_formacion.clave_acceso', 'apunts')
