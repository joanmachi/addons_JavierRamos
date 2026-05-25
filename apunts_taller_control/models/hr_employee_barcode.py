from odoo import models
from odoo.exceptions import UserError


class HrEmployeeBarcode(models.Model):
    _inherit = "hr.employee"

    def buscar_empleado(self, barcode):
        res = super().buscar_empleado(barcode)
        if res:
            emp = self.browse(res[0]["id"])
            if emp.exists() and emp.apunts_taller_bloqueado:
                motivo = emp.apunts_taller_motivo_bloqueo or "sin motivo registrado"
                raise UserError(
                    "Empleado %s bloqueado en taller.\n\n"
                    "Motivo: %s\n\n"
                    "Pasa por oficina para que te desbloqueen antes de fichar."
                    % (emp.name, motivo)
                )
        return res
