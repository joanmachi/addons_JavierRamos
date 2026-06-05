from odoo import _, api, fields, models


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

    motivo = fields.Char(
        string='Motivo de la corrección',
        help='Texto libre para auditoría en el chatter del empleado.',
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

    # ── Acción principal ──────────────────────────────────────────────────────

    def action_aplicar(self):
        self.ensure_one()
        Productivity = self.env['mrp.workcenter.productivity']

        if self.tiene_fichaje_abierto:
            # CASO 1: cerrar el fichaje abierto con hora corregida
            # Usar el workorder seleccionado si el admin lo cambió
            if self.workorder_id_abierto:
                prod = Productivity.search([
                    ('employee_id', '=', self.employee_id.id),
                    ('workorder_id', '=', self.workorder_id_abierto.id),
                    ('date_end', '=', False),
                ], limit=1) or self.productivity_abierta_id
            else:
                prod = self.productivity_abierta_id
            if prod:
                prod.write({'date_end': self.salida_real})
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
                # Resolver loss_id sin depender del nombre del modelo
                # (mrp.workcenter.loss puede no estar registrado en Odoo 18)
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
                }
                if loss_id:
                    vals_prod['loss_id'] = loss_id
                nuevo = Productivity.create(vals_prod)
                accion_msg = (
                    f"Nuevo fichaje creado (id {nuevo.id}) en "
                    f"{self.workorder_id_nuevo.production_id.name} / {self.workorder_id_nuevo.name}: "
                    f"{fields.Datetime.to_string(self.date_start_nuevo)} → "
                    f"{fields.Datetime.to_string(self.date_end_nuevo)}."
                )
            else:
                accion_msg = "No se creó fichaje (falta fase o fecha de inicio) — solo se desbloqueó al operario."

        # Desbloquear siempre
        if self.employee_id.apunts_taller_bloqueado:
            self.employee_id.write({
                'apunts_taller_bloqueado': False,
                'apunts_taller_motivo_bloqueo': False,
                'apunts_taller_fecha_bloqueo': False,
            })

        msg = _("Desbloqueo manual por %(user)s.\n%(accion)s") % {
            'user': self.env.user.name,
            'accion': accion_msg,
        }
        if self.motivo:
            msg += _("\nMotivo: %s") % self.motivo
        self.employee_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
