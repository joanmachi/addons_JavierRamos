from odoo import api, fields, models


class MrpWorkcenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    apunts_duracion_viva = fields.Float(
        string='Duración (h)',
        compute='_compute_apunts_duracion_viva',
        aggregator='sum',
        help='Si el fichaje sigue abierto: tiempo desde date_start hasta ahora. '
             'Si está cerrado: duracion final.',
    )
    apunts_production_id = fields.Many2one(
        related='workorder_id.production_id',
        string='OF',
        store=True,
    )
    apunts_dia = fields.Date(
        string='Día',
        compute='_compute_apunts_dia',
        store=False,
        help='Día (fecha) del date_start, usable para agrupar.',
    )
    apunts_emp_bloqueado = fields.Boolean(
        related='employee_id.apunts_taller_bloqueado', string='Bloqueado',
    )
    apunts_emp_motivo_bloqueo = fields.Char(
        related='employee_id.apunts_taller_motivo_bloqueo', string='Motivo bloqueo',
    )
    apunts_emp_horas_hoy = fields.Float(
        related='employee_id.apunts_horas_hoy', string='Horas HOY',
    )
    apunts_emp_horas_semana = fields.Float(
        related='employee_id.apunts_horas_semana', string='Horas semana',
    )

    def action_apunts_desbloquear_emp(self):
        for rec in self:
            if rec.employee_id:
                rec.employee_id.action_apunts_desbloquear_taller()
        return True

    @api.depends('date_start', 'date_end')
    def _compute_apunts_duracion_viva(self):
        ahora = fields.Datetime.now()
        for rec in self:
            if not rec.date_start:
                rec.apunts_duracion_viva = 0.0
                continue
            fin = rec.date_end or ahora
            delta = fin - rec.date_start
            rec.apunts_duracion_viva = delta.total_seconds() / 3600.0

    @api.depends('date_start')
    def _compute_apunts_dia(self):
        for rec in self:
            rec.apunts_dia = rec.date_start.date() if rec.date_start else False

    def action_apunts_ver_of(self):
        self.ensure_one()
        if not self.apunts_production_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.apunts_production_id.name,
            'res_model': 'mrp.production',
            'res_id': self.apunts_production_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_apunts_cerrar_ahora(self):
        ahora = fields.Datetime.now()
        for rec in self:
            if rec.date_end:
                continue
            rec.write({'date_end': ahora})
            if rec.workorder_id and rec.workorder_id.production_id:
                rec.workorder_id.production_id.message_post(body=(
                    "Fichaje cerrado manualmente por %s. "
                    "Operario: %s · Inicio: %s · Cierre: %s."
                ) % (
                    self.env.user.name,
                    rec.employee_id.name or '?',
                    fields.Datetime.to_string(rec.date_start),
                    fields.Datetime.to_string(ahora),
                ))
        return True
