"""Rellena la compañía de los desbloqueos ya guardados (campo nuevo, la toma
del operario) para que la regla multiempresa nueva los filtre bien."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        UPDATE apunts_taller_desbloqueo d
           SET company_id = e.company_id
          FROM hr_employee e
         WHERE e.id = d.employee_id
           AND d.company_id IS DISTINCT FROM e.company_id
    """)
    _logger.info("Desbloqueos con compañía rellenada: %s", cr.rowcount)
