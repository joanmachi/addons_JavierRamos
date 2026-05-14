from . import models


def post_init_hook(env):
    env['mrp.production']._apunts_get_studio_sale_field()


