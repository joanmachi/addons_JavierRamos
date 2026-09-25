"""Marcar como operarios de planta a los empleados que fichan en órdenes del
taller (últimos 90 días), salvo los excluidos del rendimiento (empresa,
gestión, pruebas). La empresa lo ajusta en la ficha del empleado."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT column_name FROM information_schema.columns "
               "WHERE table_name = 'hr_employee' AND column_name = 'apunts_excluir_rendimiento'")
    excl = "AND COALESCE(e.apunts_excluir_rendimiento, FALSE) = FALSE" if cr.fetchone() else ""
    cr.execute("""
        SELECT DISTINCT e.id FROM hr_employee e
        JOIN mrp_workcenter_productivity p ON p.employee_id = e.id
        WHERE e.active AND p.date_end >= NOW() - INTERVAL '90 days' %s""" % excl)
    ids = [r[0] for r in cr.fetchall()]
    if ids:
        env["hr.employee"].browse(ids).write({"apunts_planta": True})
    _logger.info("Operarios de planta marcados de inicio: %s", len(ids))
