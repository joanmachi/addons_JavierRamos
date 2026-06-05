from odoo import _, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    apunts_taller_bloqueado = fields.Boolean(
        string="Bloqueado en taller",
        default=False,
        tracking=True,
        help=(
            "Cuando está activado, el empleado no puede iniciar nuevos "
            "fichajes desde la vista taller ni hacer toggle de asistencia. "
            "Se activa automáticamente por los crons de control "
            "(>9h continuas en una OF, >5 min sin fichaje activo, etc.). "
            "Solo desbloqueable manualmente desde oficina."
        ),
    )
    apunts_taller_motivo_bloqueo = fields.Char(
        string="Motivo del bloqueo",
        readonly=True,
    )
    apunts_taller_fecha_bloqueo = fields.Datetime(
        string="Fecha del bloqueo",
        readonly=True,
    )

    def action_apunts_desbloquear_taller(self):
        self.ensure_one()
        # Detectar caso: ¿tiene fichaje abierto?
        prod_abierta = self.env['mrp.workcenter.productivity'].search([
            ('employee_id', '=', self.id),
            ('date_end', '=', False),
        ], order='date_start DESC', limit=1)

        vals = {
            'employee_id': self.id,
            'motivo_bloqueo': self.apunts_taller_motivo_bloqueo or '',
            'fecha_bloqueo': self.apunts_taller_fecha_bloqueo,
        }

        if prod_abierta:
            # CASO 1: fichado demasiado tiempo → pre-cargar la OF
            vals['production_id'] = prod_abierta.workorder_id.production_id.id or False
        else:
            # CASO 2: inactividad → pre-cargar fechas para el nuevo fichaje
            last_prod = self.env['mrp.workcenter.productivity'].search([
                ('employee_id', '=', self.id),
                ('date_end', '!=', False),
            ], order='date_end DESC', limit=1)
            if last_prod:
                vals['date_start_nuevo'] = last_prod.date_end
            else:
                # Fallback: desde el check_in de asistencia del día
                att = self.env['hr.attendance'].search([
                    ('employee_id', '=', self.id),
                    ('check_out', '=', False),
                ], limit=1)
                if att:
                    vals['date_start_nuevo'] = att.check_in
            vals['date_end_nuevo'] = self.apunts_taller_fecha_bloqueo or fields.Datetime.now()

        wizard = self.env['apunts.corregir.fichaje.wizard'].sudo().create(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Desbloquear operario — %s') % self.name,
            'res_model': 'apunts.corregir.fichaje.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
