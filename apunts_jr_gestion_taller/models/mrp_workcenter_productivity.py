from datetime import timedelta

from odoo import _, api, fields, models


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
        string='OF (ref)',
        store=True,
    )
    apunts_of_short = fields.Char(
        string='OF',
        compute='_compute_apunts_of_short',
        store=True,
        help='Nombre corto de la OF: name sin prefijo "FAB/MO/".',
    )
    apunts_ot_short = fields.Char(
        string='OT (fase)',
        compute='_compute_apunts_ot_short',
        store=True,
        help='Nombre corto de la OT (workorder): name sin prefijo "FAB/MO/".',
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

    # ── Trazabilidad de fichajes modificados/creados manualmente ──────────────
    # Permite ver en el histórico qué operarios fallan en el fichaje (para
    # formación) y filtrar por fichadas modificadas y por el motivo.
    apunts_modificado_manual = fields.Boolean(
        string='Modificado manual', default=False, index=True,
        help='Marcado cuando el fichaje se creó o corrigió manualmente desde '
             'oficina (wizard de desbloqueo/corrección).',
    )
    apunts_motivo_correccion = fields.Selection(
        selection=[
            ('falta_of', 'Falta OF'),
            ('responsabilidad_operario', 'Responsabilidad operario'),
            ('fuerza_mayor', 'Fuerza mayor'),
        ],
        string='Motivo corrección',
        help='Motivo de la corrección/creación manual del fichaje.',
    )
    apunts_modificado_por_id = fields.Many2one(
        'res.users', string='Modificado por', readonly=True,
    )
    apunts_modificado_fecha = fields.Datetime(
        string='Fecha modificación', readonly=True,
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

    @api.depends('workorder_id.production_id.name')
    def _compute_apunts_of_short(self):
        for rec in self:
            name = (rec.workorder_id.production_id.name or '') if rec.workorder_id else ''
            rec.apunts_of_short = name.replace('FAB/MO/', '')

    @api.depends('workorder_id.name')
    def _compute_apunts_ot_short(self):
        for rec in self:
            name = (rec.workorder_id.name or '') if rec.workorder_id else ''
            rec.apunts_ot_short = name.replace('FAB/MO/', '')

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

    def create(self, vals_list):
        """Si al crear un fichaje de OF en vivo el empleado no tiene asistencia
        abierta, crea una automáticamente con check_in = date_start.

        El write() sync se encargará de ajustar el check_in si el barcode
        module retrotrae el date_start (backdating por inactividad breve).
        No aplica a registros retroactivos (date_start > 1 h en el pasado)
        ni cuando ya hay una asistencia abierta."""
        records = super().create(vals_list)
        _SYNC = '_apunts_sync_fichaje'
        if not self.env.context.get(_SYNC):
            Att = self.env['hr.attendance'].sudo()
            ahora = fields.Datetime.now()
            for rec in records:
                if not rec.employee_id or not rec.date_start:
                    continue
                # Ignorar fichajes retroactivos (wizard de corrección, etc.)
                if (ahora - rec.date_start).total_seconds() > 3600:
                    continue
                # Solo crear si no hay asistencia abierta
                open_att = Att.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('check_out', '=', False),
                ], limit=1)
                if not open_att:
                    Att.create({
                        'employee_id': rec.employee_id.id,
                        'check_in': rec.date_start,
                    })
        return records

    def write(self, vals):
        """Sincroniza hr.attendance.check_in cuando date_start cambia.

        Si el fichaje que se modifica es el primero del día (su date_start
        coincidía con el check_in de la asistencia ±1 min), actualiza el
        check_in para mantener coherencia. Tolera modificaciones de días
        anteriores. Flag _apunts_sync_fichaje evita bucles."""
        _SYNC = '_apunts_sync_fichaje'
        old_starts = {}
        if 'date_start' in vals and not self.env.context.get(_SYNC):
            for rec in self:
                if rec.date_start and rec.employee_id:
                    old_starts[rec.id] = rec.date_start

        result = super().write(vals)

        if old_starts:
            tol = timedelta(seconds=60)
            Att = self.env['hr.attendance'].sudo()
            for rec in self:
                old = old_starts.get(rec.id)
                if not old or not rec.date_start or old == rec.date_start:
                    continue
                att = Att.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('check_in', '>=', old - tol),
                    ('check_in', '<=', old + tol),
                ], order='check_in asc', limit=1)
                if att:
                    att.with_context(**{_SYNC: True}).write(
                        {'check_in': rec.date_start}
                    )
        return result

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

    def action_apunts_reasignar_fichaje(self):
        """Abre el wizard para mover este fichaje a otra OF/fase, conservando
        las fechas. Funciona también con el fichaje abierto (sin salida)."""
        self.ensure_one()
        wizard = self.env['apunts.reasignar.fichaje.wizard'].create({
            'productivity_id': self.id,
            'workorder_origen_id': self.workorder_id.id,
            'production_origen_id': self.workorder_id.production_id.id,
            'production_id': self.workorder_id.production_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reasignar fichaje'),
            'res_model': 'apunts.reasignar.fichaje.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
