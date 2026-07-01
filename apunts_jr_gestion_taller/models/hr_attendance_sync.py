from datetime import timedelta

from odoo import fields, models


class HrAttendanceSync(models.Model):
    _inherit = 'hr.attendance'

    def write(self, vals):
        """Sincroniza mrp.workcenter.productivity.date_start cuando check_in cambia.

        Si el check_in modificado coincidía con el date_start de algún fichaje
        de OF del mismo empleado (±1 min), actualiza ese date_start también.
        Tolera modificaciones de días anteriores.
        Flag _apunts_sync_fichaje evita bucles."""
        _SYNC = '_apunts_sync_fichaje'
        old_checkins = {}
        if 'check_in' in vals and not self.env.context.get(_SYNC):
            for rec in self:
                if rec.check_in and rec.employee_id:
                    old_checkins[rec.id] = rec.check_in

        result = super().write(vals)

        if old_checkins:
            tol = timedelta(seconds=60)
            Prod = self.env['mrp.workcenter.productivity'].sudo()
            for rec in self:
                old = old_checkins.get(rec.id)
                if not old or not rec.check_in or old == rec.check_in:
                    continue
                prods = Prod.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('date_start', '>=', old - tol),
                    ('date_start', '<=', old + tol),
                ])
                if prods:
                    prods.with_context(**{_SYNC: True}).write(
                        {'date_start': rec.check_in}
                    )
        return result
