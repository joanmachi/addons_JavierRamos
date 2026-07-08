from . import models


def post_init_hook(env):
    """Primera foto semanal al instalar: la historia empieza cuanto antes."""
    env["apunts.direccion.snapshot"].cron_tomar_foto()
