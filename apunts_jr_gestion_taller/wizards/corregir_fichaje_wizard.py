import re
from datetime import datetime, time, timedelta
from pytz import timezone, utc

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ApuntsCorregirFichajeWizard(models.TransientModel):
    _name = 'apunts.corregir.fichaje.wizard'
    _description = 'Wizard gestión: corregir fichaje y desbloquear empleado'

    employee_id = fields.Many2one(
        'hr.employee', string='Operario', required=True,
    )
    motivo_bloqueo = fields.Char(
        string='Motivo del bloqueo', readonly=True,
    )
    fecha_bloqueo = fields.Datetime(
        string='Bloqueado desde', readonly=True,
    )

    # ── Detección del caso ────────────────────────────────────────────────────

    tiene_fichaje_abierto = fields.Boolean(
        compute='_compute_tiene_fichaje_abierto',
    )
    productivity_abierta_id = fields.Many2one(
        'mrp.workcenter.productivity',
        compute='_compute_tiene_fichaje_abierto',
    )

    @api.depends('employee_id')
    def _compute_tiene_fichaje_abierto(self):
        for w in self:
            if not w.employee_id:
                w.tiene_fichaje_abierto = False
                w.productivity_abierta_id = False
                continue
            prod = self.env['mrp.workcenter.productivity'].search([
                ('employee_id', '=', w.employee_id.id),
                ('date_end', '=', False),
            ], order='date_start DESC', limit=1)
            w.tiene_fichaje_abierto = bool(prod)
            w.productivity_abierta_id = prod

    # ── OFs disponibles (filtradas por employee o todas) ──────────────────────

    mostrar_todas_ofs = fields.Boolean(string='Buscar en TODAS las OFs', default=False)
    ofs_filtradas_ids = fields.Many2many(
        'mrp.production', compute='_compute_ofs_filtradas_ids',
    )

    @api.depends('employee_id', 'mostrar_todas_ofs')
    def _compute_ofs_filtradas_ids(self):
        for w in self:
            if w.mostrar_todas_ofs or not w.employee_id:
                w.ofs_filtradas_ids = self.env['mrp.production'].search([
                    ('state', 'in', ('confirmed', 'progress', 'to_close', 'done')),
                ])
            else:
                prods = self.env['mrp.workcenter.productivity'].search([
                    ('employee_id', '=', w.employee_id.id),
                ])
                w.ofs_filtradas_ids = prods.mapped('workorder_id.production_id')

    # ── CASO 1: fichado demasiado tiempo ──────────────────────────────────────
    # OF pre-cargada (editable), OT dentro de esa OF, "fichado desde", salida corregida

    production_id = fields.Many2one(
        'mrp.production', string='Orden de Fabricación',
        domain="[('id', 'in', ofs_filtradas_ids)]",
    )
    workorder_id_abierto = fields.Many2one(
        'mrp.workorder', string='Fase (OT)',
        domain="[('production_id', '=', production_id), ('state', 'not in', ('cancel',))]",
    )
    date_start_abierto = fields.Datetime(
        string='Fichado desde',
        compute='_compute_date_start_abierto',
        store=False,
    )
    salida_real = fields.Datetime(
        string='Corregir salida a',
        default=fields.Datetime.now,
    )

    @api.depends('productivity_abierta_id', 'workorder_id_abierto', 'employee_id')
    def _compute_date_start_abierto(self):
        Prod = self.env['mrp.workcenter.productivity']
        for w in self:
            # Preferir la productivity del workorder seleccionado si cambió
            if w.workorder_id_abierto:
                p = Prod.search([
                    ('employee_id', '=', w.employee_id.id),
                    ('workorder_id', '=', w.workorder_id_abierto.id),
                    ('date_end', '=', False),
                ], limit=1)
                w.date_start_abierto = p.date_start if p else False
            elif w.productivity_abierta_id:
                w.date_start_abierto = w.productivity_abierta_id.date_start
            else:
                w.date_start_abierto = False

    # ── CASO 2: inactividad — crear nuevo fichaje ─────────────────────────────

    workorder_id_nuevo = fields.Many2one(
        'mrp.workorder', string='Fase (OT)',
        domain="[('production_id', '=', production_id), ('state', 'not in', ('cancel',))]",
    )
    date_start_nuevo = fields.Datetime(string='Inicio del periodo')
    date_end_nuevo = fields.Datetime(string='Fin del periodo', default=fields.Datetime.now)

    # ── Campos comunes ────────────────────────────────────────────────────────

    motivo = fields.Selection(
        selection=[
            ('falta_of', 'Falta OF'),
            ('responsabilidad_operario', 'Responsabilidad operario'),
            ('fuerza_mayor', 'Fuerza mayor'),
        ],
        string='Motivo de la corrección',
        help='Motivo de la corrección. Obligatorio solo si se corrige o se crea un fichaje.',
    )
    fichajes_editables_ids = fields.Many2many(
        'mrp.workcenter.productivity',
        compute='_compute_fichajes_editables_ids',
        string='Fichajes del operario',
    )

    @api.depends('employee_id')
    def _compute_fichajes_editables_ids(self):
        for w in self:
            if not w.employee_id:
                w.fichajes_editables_ids = False
                continue
            w.fichajes_editables_ids = self.env['mrp.workcenter.productivity'].search(
                [('employee_id', '=', w.employee_id.id)],
                order='date_start DESC',
                limit=100,
            )

    # ── Ausencias automáticas ─────────────────────────────────────────────────

    def _leave_type(self):
        """Busca el tipo de ausencia más adecuado: primero por horas sin
        asignación, luego sin asignación, luego cualquiera activo."""
        LeaveType = self.env['hr.leave.type'].sudo()
        for domain in [
            [('active', '=', True), ('requires_allocation', '=', 'no'), ('request_unit', '=', 'hour')],
            [('active', '=', True), ('requires_allocation', '=', 'no')],
            [('active', '=', True)],
        ]:
            lt = LeaveType.search(domain, order='sequence asc, id asc', limit=1)
            if lt:
                return lt
        return LeaveType

    def _crear_leave(self, emp, dia, horas_faltantes, sufijo=''):
        """Crea el hr.leave en borrador anclado al día y horas correctas.

        date_from/date_to son readonly+computed en Odoo 18 → se pasan
        request_date_from/request_date_to (anclan el día) y se fuerza
        request_unit_hours=True ("Horas personalizadas") con el rango de
        horas exacto, independientemente del tipo de ausencia (día/hora)."""
        leave_type = self._leave_type()
        if not leave_type:
            return None

        # Limitar a 23:59 para no superar el día
        hora_fin = min(round(8.0 + horas_faltantes, 2), 23.99)

        vals = {
            'employee_id': emp.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': dia,
            'request_date_to': dia,
            'request_unit_hours': True,      # "Horas personalizadas" → ignora tipo día/hora
            'request_hour_from': 8.0,        # 08:00 local como inicio referencial
            'request_hour_to': hora_fin,     # 08:00 + horas_faltantes
            'private_name': _(
                'Jornada incompleta %s — creada automáticamente al desbloquear%s'
            ) % (fields.Date.to_string(dia), sufijo),
        }

        try:
            return self.env['hr.leave'].sudo().create(vals)
        except Exception:
            return None

    def _crear_ausencia_caso1(self, prod):
        """CASO 1 (fichaje continuo / OF abierta): tras corregir el fichaje,
        calcula las horas fichadas en el día del incidente y crea ausencia en
        borrador si la jornada quedó incompleta.

        El día de referencia es la fecha local del date_start del fichaje abierto.
        Las horas fichadas se suman de todos los registros de productividad cerrados
        ese día (incluyendo el que se acaba de cerrar con salida_real)."""
        if not prod:
            return None
        emp = self.employee_id
        emp_tz = timezone(emp._apunts_tz())

        # Día local del inicio del fichaje (cuándo empezó a trabajar el operario)
        dia = utc.localize(prod.date_start.replace(tzinfo=None)).astimezone(emp_tz).date()

        esperadas = emp._apunts_horas_esperadas(dia)
        if not esperadas:
            return None

        # Límites del día en UTC
        day_from = emp_tz.localize(datetime.combine(dia, time.min)).astimezone(utc).replace(tzinfo=None)
        day_to = emp_tz.localize(datetime.combine(dia, time.max)).astimezone(utc).replace(tzinfo=None)

        # Suma de horas de productividad cerradas ese día (capped al día)
        fichs = self.env['mrp.workcenter.productivity'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date_start', '>=', day_from),
            ('date_start', '<=', day_to),
            ('date_end', '!=', False),
        ])
        horas_fichadas = sum(
            (min(f.date_end, day_to) - max(f.date_start, day_from)).total_seconds() / 3600.0
            for f in fichs
            if min(f.date_end, day_to) > max(f.date_start, day_from)
        )

        aus = emp._apunts_horas_ausencia(dia)
        horas_faltantes = esperadas - horas_fichadas - aus
        if horas_faltantes <= 0:
            return None

        return self._crear_leave(emp, dia, horas_faltantes, sufijo=' (fichaje corregido)')

    def _crear_ausencia_jornada_insuficiente(self):
        """CASO 2 (sin fichaje abierto, bloqueo por jornada insuficiente): crea
        ausencia en borrador si no se realizó ninguna corrección de fichaje.
        La fecha se extrae del motivo del bloqueo ('Jornada insuficiente el YYYY-MM-DD')."""
        motivo = self.motivo_bloqueo or ''
        if 'Jornada insuficiente' not in motivo:
            return None
        if self.workorder_id_nuevo and self.date_start_nuevo:
            return None  # se corrigió el fichaje → no crear ausencia

        m = re.search(r'(\d{4}-\d{2}-\d{2})', motivo)
        if not m:
            return None
        dia = fields.Date.from_string(m.group(1))

        emp = self.employee_id
        esperadas = emp._apunts_horas_esperadas(dia)
        if not esperadas:
            return None
        pres = emp._apunts_horas_presencia(dia)
        aus = emp._apunts_horas_ausencia(dia)
        horas_faltantes = esperadas - (pres + aus)
        if horas_faltantes <= 0:
            return None

        return self._crear_leave(emp, dia, horas_faltantes)

    # ── Acción principal ──────────────────────────────────────────────────────

    def action_aplicar(self):
        self.ensure_one()
        Productivity = self.env['mrp.workcenter.productivity']
        prod_cerrado = None  # fichaje de CASO 1 que se cierra → para crear ausencia
        of_vinculada_id = False  # OF de la corrección → para el histórico de desbloqueos

        if self.tiene_fichaje_abierto:
            # CASO 1: cerrar el fichaje abierto con hora corregida
            if self.workorder_id_abierto:
                prod = Productivity.search([
                    ('employee_id', '=', self.employee_id.id),
                    ('workorder_id', '=', self.workorder_id_abierto.id),
                    ('date_end', '=', False),
                ], limit=1) or self.productivity_abierta_id
            else:
                prod = self.productivity_abierta_id
            if prod:
                if not self.motivo:
                    raise UserError(_(
                        "Indica el motivo de la corrección para cerrar el fichaje abierto."))
                prod.write({
                    'date_end': self.salida_real,
                    'apunts_modificado_manual': True,
                    'apunts_motivo_correccion': self.motivo,
                    'apunts_modificado_por_id': self.env.user.id,
                    'apunts_modificado_fecha': fields.Datetime.now(),
                })
                prod_cerrado = prod  # guardar para calcular ausencia tras el cierre
                of_vinculada_id = prod.workorder_id.production_id.id or False
                accion_msg = (
                    f"Fichaje cerrado (id {prod.id}) en "
                    f"{prod.workorder_id.production_id.name} / {prod.workorder_id.name} "
                    f"— entrada {fields.Datetime.to_string(prod.date_start)} "
                    f"→ salida corregida {fields.Datetime.to_string(self.salida_real)}."
                )
            else:
                accion_msg = "No se encontró fichaje abierto — solo se desbloqueó al operario."
        else:
            # CASO 2: crear nuevo fichaje para el periodo sin fichar
            nuevo = False
            if self.workorder_id_nuevo and self.date_start_nuevo:
                if not self.motivo:
                    raise UserError(_(
                        "Indica el motivo de la corrección para crear el nuevo fichaje."))
                loss_id = False
                loss_field = Productivity._fields.get('loss_id')
                if loss_field and loss_field.comodel_name in self.env.registry:
                    loss = self.env[loss_field.comodel_name].search(
                        [('loss_type', '=', 'productive')], limit=1
                    )
                    loss_id = loss.id
                if not loss_id:
                    ref = Productivity.search([('loss_id', '!=', False)], limit=1)
                    loss_id = ref.loss_id.id if ref else False

                vals_prod = {
                    'workorder_id': self.workorder_id_nuevo.id,
                    'workcenter_id': self.workorder_id_nuevo.workcenter_id.id,
                    'employee_id': self.employee_id.id,
                    'date_start': self.date_start_nuevo,
                    'date_end': self.date_end_nuevo or fields.Datetime.now(),
                    'description': f'Fichaje creado manualmente por {self.env.user.name}',
                    'apunts_modificado_manual': True,
                    'apunts_motivo_correccion': self.motivo,
                    'apunts_modificado_por_id': self.env.user.id,
                    'apunts_modificado_fecha': fields.Datetime.now(),
                }
                if loss_id:
                    vals_prod['loss_id'] = loss_id
                nuevo = Productivity.create(vals_prod)
                of_vinculada_id = self.workorder_id_nuevo.production_id.id or False
                accion_msg = (
                    f"Nuevo fichaje creado (id {nuevo.id}) en "
                    f"{self.workorder_id_nuevo.production_id.name} / {self.workorder_id_nuevo.name}: "
                    f"{fields.Datetime.to_string(self.date_start_nuevo)} → "
                    f"{fields.Datetime.to_string(self.date_end_nuevo)}."
                )
            else:
                accion_msg = "No se creó fichaje (falta fase o fecha de inicio) — solo se desbloqueó al operario."

        # Ausencia automática SOLO en CASO 2 con bloqueo por jornada insuficiente.
        # En CASO 1 (fichaje continuo) no se crea: no se sabe si el operario
        # trabajó o no su jornada, solo se corrige el fichaje abierto.
        ausencia = (
            None
            if prod_cerrado
            else self._crear_ausencia_jornada_insuficiente()
        )

        motivo_label = (
            dict(self._fields['motivo'].selection).get(self.motivo, self.motivo)
            if self.motivo else False
        )

        # Desbloquear siempre (el write dispara el histórico de desbloqueos;
        # el contexto enriquece la traza con lo que se hizo en el wizard)
        if self.employee_id.apunts_taller_bloqueado:
            info_desbloqueo = {
                'accion': accion_msg,
                'con_correccion': bool(of_vinculada_id),
                'production_id': of_vinculada_id,
                'motivo_correccion': motivo_label,
                'ausencia_id': ausencia.id if ausencia else False,
            }
            self.employee_id.with_context(
                apunts_desbloqueo_info=info_desbloqueo
            ).write({
                'apunts_taller_bloqueado': False,
                'apunts_taller_motivo_bloqueo': False,
                'apunts_taller_fecha_bloqueo': False,
            })

        msg = _("Desbloqueo manual por %(user)s.\n%(accion)s") % {
            'user': self.env.user.name,
            'accion': accion_msg,
        }
        if motivo_label:
            msg += _("\nMotivo: %s") % motivo_label
        if ausencia:
            horas = round(
                (ausencia.date_to - ausencia.date_from).total_seconds() / 3600.0, 2
            ) if (ausencia.date_from and ausencia.date_to) else '?'
            m_dia = re.search(r'(\d{4}-\d{2}-\d{2})', ausencia.name or '')
            dia_str = m_dia.group(1) if m_dia else '?'
            msg += _(
                "\nAusencia en borrador creada automáticamente: tipo «%s», %.2f h el %s. "
                "Revísala en RRHH → Ausencias y apruébala o ajusta el tipo si procede."
            ) % (ausencia.holiday_status_id.name, horas, dia_str)
        self.employee_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
