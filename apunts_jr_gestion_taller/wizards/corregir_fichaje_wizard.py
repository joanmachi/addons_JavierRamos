from odoo import _, api, fields, models


class ApuntsCorregirFichajeWizard(models.TransientModel):
    _name = 'apunts.corregir.fichaje.wizard'
    _description = 'Wizard gestión: corregir fichaje y desbloquear empleado'

    employee_id = fields.Many2one(
        'hr.employee', string='Operario', required=True,
    )
    motivo_bloqueo = fields.Char(
        string='Motivo del bloqueo', readonly=True,
        help='Razón por la que el operario fue bloqueado automáticamente.',
    )
    fecha_bloqueo = fields.Datetime(
        string='Bloqueado desde', readonly=True,
    )

    # ── Detección automática del caso ────────────────────────────────────────

    tiene_fichaje_abierto = fields.Boolean(
        compute='_compute_tiene_fichaje_abierto',
        help='True si el operario tiene un fichaje abierto (caso: fichado demasiado tiempo).',
    )
    productivity_abierta_id = fields.Many2one(
        'mrp.workcenter.productivity',
        compute='_compute_tiene_fichaje_abierto',
        string='Fichaje abierto',
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

    # ── CASO 1: fichado demasiado tiempo → cerrar con hora corregida ─────────

    mostrar_todas_ofs = fields.Boolean(
        string='Buscar en TODAS las OFs',
        default=False,
        help='Por defecto solo se muestran las OFs donde el operario tiene fichajes. '
             'Marca esto si necesitas elegir una OF en la que NO haya trabajado todavía.',
    )
    production_id = fields.Many2one(
        'mrp.production', string='Orden de Fabricación',
        domain="[('id', 'in', ofs_filtradas_ids)]",
    )
    ofs_filtradas_ids = fields.Many2many(
        'mrp.production',
        string='OFs filtradas',
        compute='_compute_ofs_filtradas_ids',
    )
    salida_real = fields.Datetime(
        string='Salida real (hora corregida)',
        default=fields.Datetime.now,
        help='Hora a la que se cerrará el fichaje abierto del operario.',
    )
    motivo = fields.Char(
        string='Motivo de la corrección (opcional)',
        help='Texto libre para auditoría en el chatter del empleado.',
    )
    fichajes_operario_of_html = fields.Html(
        string='Fichajes del operario en esta OF',
        compute='_compute_fichajes_operario_of_html',
    )
    fichajes_editables_ids = fields.Many2many(
        'mrp.workcenter.productivity',
        compute='_compute_fichajes_editables_ids',
        string='Fichajes editables (entrada/salida)',
    )

    # ── CASO 2: inactividad → crear nuevo fichaje ─────────────────────────────

    workorder_id_nuevo = fields.Many2one(
        'mrp.workorder', string='Fase (OT)',
        domain="[('production_id', '=', production_id), ('state', 'not in', ('cancel',))]",
        help='Selecciona la fase/orden de trabajo dentro de la OF donde estuvo el operario.',
    )
    date_start_nuevo = fields.Datetime(
        string='Inicio del periodo',
        help='Hora a la que el operario empezó a trabajar (se creará un fichaje desde aquí).',
    )
    date_end_nuevo = fields.Datetime(
        string='Fin del periodo',
        default=fields.Datetime.now,
        help='Hora a la que el operario paró de trabajar.',
    )

    # ── Computados auxiliares ─────────────────────────────────────────────────

    productividades_abiertas_html = fields.Html(
        string='Fichajes abiertos ahora',
        compute='_compute_productividades_abiertas_html',
    )

    @api.depends('employee_id', 'mostrar_todas_ofs')
    def _compute_ofs_filtradas_ids(self):
        for w in self:
            if w.mostrar_todas_ofs or not w.employee_id:
                w.ofs_filtradas_ids = self.env['mrp.production'].search([
                    ('state', 'in', ('progress', 'done', 'to_close', 'confirmed')),
                ])
            else:
                productivities = self.env['mrp.workcenter.productivity'].search([
                    ('employee_id', '=', w.employee_id.id),
                ])
                ofs = productivities.mapped('workorder_id.production_id')
                w.ofs_filtradas_ids = ofs

    @api.depends('employee_id', 'production_id')
    def _compute_fichajes_operario_of_html(self):
        for w in self:
            if not (w.employee_id and w.production_id):
                w.fichajes_operario_of_html = (
                    "<p><em>Selecciona operario y OF para ver sus fichajes en esa OF.</em></p>"
                )
                continue
            registros = self.env['mrp.workcenter.productivity'].search(
                [
                    ('employee_id', '=', w.employee_id.id),
                    ('workorder_id.production_id', '=', w.production_id.id),
                ],
                order='date_start ASC',
            )
            if not registros:
                w.fichajes_operario_of_html = (
                    "<p><em>%s no tiene fichajes en %s.</em></p>"
                ) % (w.employee_id.name, w.production_id.name)
                continue
            filas = []
            for r in registros:
                wo = r.workorder_id.name or '?'
                ini = fields.Datetime.to_string(r.date_start) if r.date_start else '?'
                fin = (fields.Datetime.to_string(r.date_end) if r.date_end
                       else '<strong style="color:#c00">ABIERTO</strong>')
                if r.date_start and r.date_end:
                    horas = (r.date_end - r.date_start).total_seconds() / 3600.0
                    dur = f"{horas:.2f} h"
                elif r.date_start:
                    horas = (fields.Datetime.now() - r.date_start).total_seconds() / 3600.0
                    dur = f"{horas:.2f} h (corriendo)"
                else:
                    dur = '?'
                filas.append(
                    f"<tr><td>{wo}</td><td>{ini}</td><td>{fin}</td><td>{dur}</td></tr>"
                )
            w.fichajes_operario_of_html = (
                "<table class='table table-sm'>"
                "<thead><tr><th>OT</th><th>Inicio</th><th>Fin</th><th>Duración</th></tr></thead>"
                f"<tbody>{''.join(filas)}</tbody></table>"
            )

    @api.depends('employee_id')
    def _compute_fichajes_editables_ids(self):
        for w in self:
            if not w.employee_id:
                w.fichajes_editables_ids = False
                continue
            registros = self.env['mrp.workcenter.productivity'].search(
                [('employee_id', '=', w.employee_id.id)],
                order='date_start DESC',
                limit=200,
            )
            w.fichajes_editables_ids = registros

    @api.depends('employee_id')
    def _compute_productividades_abiertas_html(self):
        Productivity = self.env['mrp.workcenter.productivity']
        for w in self:
            domain = [('date_end', '=', False), ('employee_id', '!=', False)]
            registros = Productivity.search(domain, order='date_start ASC')
            if not registros:
                w.productividades_abiertas_html = '<p><em>No hay fichajes abiertos ahora mismo.</em></p>'
                continue
            filas = []
            for r in registros:
                of_name = r.workorder_id.production_id.name or '?'
                wo_name = r.workorder_id.name or '?'
                emp_name = r.employee_id.name or '?'
                inicio = fields.Datetime.to_string(r.date_start)
                filas.append(
                    f"<tr><td>{emp_name}</td><td>{of_name}</td>"
                    f"<td>{wo_name}</td><td>{inicio}</td></tr>"
                )
            w.productividades_abiertas_html = (
                "<table class='table table-sm'>"
                "<thead><tr><th>Operario</th><th>OF</th><th>OT</th><th>Inicio</th></tr></thead>"
                f"<tbody>{''.join(filas)}</tbody></table>"
            )

    # ── Acción principal ──────────────────────────────────────────────────────

    def action_aplicar(self):
        self.ensure_one()
        Productivity = self.env['mrp.workcenter.productivity']

        if self.tiene_fichaje_abierto:
            # CASO 1: cerrar el fichaje abierto con la hora corregida
            prod = self.productivity_abierta_id
            if not prod and self.production_id:
                prod = Productivity.search([
                    ('employee_id', '=', self.employee_id.id),
                    ('workorder_id.production_id', '=', self.production_id.id),
                    ('date_end', '=', False),
                ], order='date_start DESC', limit=1)
            if prod:
                prod.write({'date_end': self.salida_real})
                accion_msg = (
                    f"Fichaje cerrado (id {prod.id}) en {prod.workorder_id.production_id.name} "
                    f"— salida corregida a {fields.Datetime.to_string(self.salida_real)}."
                )
            else:
                accion_msg = "No se encontró fichaje abierto — solo se desbloqueó el empleado."
        else:
            # CASO 2: crear nuevo fichaje para el periodo sin fichar
            nuevo = False
            if self.workorder_id_nuevo and self.date_start_nuevo:
                loss = self.env['mrp.workcenter.loss'].search(
                    [('loss_type', '=', 'productive')], limit=1
                )
                vals = {
                    'workorder_id': self.workorder_id_nuevo.id,
                    'workcenter_id': self.workorder_id_nuevo.workcenter_id.id,
                    'employee_id': self.employee_id.id,
                    'date_start': self.date_start_nuevo,
                    'date_end': self.date_end_nuevo or fields.Datetime.now(),
                    'description': f'Fichaje creado manualmente por {self.env.user.name}',
                }
                if loss:
                    vals['loss_id'] = loss.id
                nuevo = Productivity.create(vals)
                accion_msg = (
                    f"Nuevo fichaje creado (id {nuevo.id}) en "
                    f"{self.workorder_id_nuevo.production_id.name} / "
                    f"{self.workorder_id_nuevo.name}: "
                    f"{fields.Datetime.to_string(self.date_start_nuevo)} → "
                    f"{fields.Datetime.to_string(self.date_end_nuevo)}."
                )
            else:
                accion_msg = "No se creó fichaje (falta fase o fecha de inicio) — solo se desbloqueó el empleado."

        # Desbloquear siempre
        if self.employee_id.apunts_taller_bloqueado:
            self.employee_id.write({
                'apunts_taller_bloqueado': False,
                'apunts_taller_motivo_bloqueo': False,
                'apunts_taller_fecha_bloqueo': False,
            })

        msg = _(
            "Desbloqueo manual por %(user)s.\n%(accion)s"
        ) % {'user': self.env.user.name, 'accion': accion_msg}
        if self.motivo:
            msg += _("\nMotivo: %s") % self.motivo
        self.employee_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
