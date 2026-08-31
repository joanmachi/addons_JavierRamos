# -*- coding: utf-8 -*-
from . import controllers
from . import models


def post_init_hook(env):
    # genera el token del enlace público si no existe
    env['formacion.ficha']._token_publico()
