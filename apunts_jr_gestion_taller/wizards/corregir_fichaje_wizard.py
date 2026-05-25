from odoo import _, api, fields, models


class ApuntsCorregirFichajeWizard(models.TransientModel):
    _name = 'apunts.corregir.fichaje.wizard'
    _description = 'Wizard gestión: corregir fichaje y desbloquear empleado'

    employee_id = fields.Many2one(
        'hr.employee', string='Operario', required=True,
    )
    mostrar_todas_ofs = fields.Boolean(
        string='Buscar en TODAS las OFs',
        default=False,
        help='Por defecto solo se muestran las OFs donde el operario tiene fichajes. '
             'Marca esto si necesitas elegir una OF en la que NO haya trabajado todavía.',
    )
    production_id = fields.Many2one(
        'mrp.production', string='Orden de Fabricación', required=True,
        domain="[('id', 'in', ofs_filtradas_ids)]",
    )
    ofs_filtradas_ids = fields.Many2many(
        'mrp.production',
        string='OFs filtradas',
        compute='_compute_ofs_filtradas_ids',
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
    salida_real = fields.Datetime(
        string='Salida real', required=True, default=fields.Datetime.now,
    )
    motivo = fields.Char(
        string='Motivo (opcional)',
        help='Texto libre para auditoría en el chatter del empleado.',
    )

    productividades_abiertas_html = fields.Html(
        string='Fichajes abiertos ahora',
        compute='_compute_productividades_abiertas_html',
    )

    @api.depends('employee_id', 'mostrar_todas_ofs')
    def _compute_ofs_filtradas_ids(self):
        for w in self:
            if w.mostrar_todas_ofs or not w.employee_id:
                w.ofs_filtradas_ids = self.env['mrp.production'].search([
                    ('state', 'in', ('progress', 'done', 'to_close')),
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
                fin = fields.Datetime.to_string(r.date_end) if r.date_end else '<strong style="color:#c00">ABIERTO</strong>'
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

    def action_aplicar(self):
        self.ensure_one()
        Productivity = self.env['mrp.workcenter.productivity']
        prod = Productivity.search([
            ('employee_id', '=', self.employee_id.id),
            ('workorder_id.production_id', '=', self.production_id.id),
            ('date_end', '=', False),
        ], order='date_start DESC', limit=1)
        if prod:
            prod.write({'date_end': self.salida_real})
        if self.employee_id.apunts_taller_bloqueado:
            self.employee_id.write({
                'apunts_taller_bloqueado': False,
                'apunts_taller_motivo_bloqueo': False,
                'apunts_taller_fecha_bloqueo': False,
            })
        accion_msg = (
            f"Productividad cerrada (id {prod.id})." if prod
            else "No había productividad abierta — solo se desbloqueó el empleado."
        )
        msg = _(
            "Fichaje corregido manualmente por %(user)s.\n"
            "OF: %(of)s\n"
            "Salida real: %(salida)s\n"
            "%(accion)s"
        ) % {
            'user': self.env.user.name,
            'of': self.production_id.name,
            'salida': self.salida_real,
            'accion': accion_msg,
        }
        if self.motivo:
            msg += "\nMotivo: %s" % self.motivo
        self.employee_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
