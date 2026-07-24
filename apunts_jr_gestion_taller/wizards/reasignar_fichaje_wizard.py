from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ApuntsReasignarFichajeWizard(models.TransientModel):
    """Reasignar un fichaje (mrp.workcenter.productivity) a otra OF o fase
    sin re-teclear fechas: se conservan date_start/date_end tal cual. Sirve
    también para fichajes ABIERTOS (sin salida): solo cambia la OF/fase y el
    operario sigue fichado en la nueva."""

    _name = 'apunts.reasignar.fichaje.wizard'
    _description = 'Reasignar fichaje a otra OF / fase'

    productivity_id = fields.Many2one(
        'mrp.workcenter.productivity', string='Fichaje', required=True, readonly=True,
    )
    employee_id = fields.Many2one(
        related='productivity_id.employee_id', string='Operario', readonly=True,
    )
    date_start = fields.Datetime(
        related='productivity_id.date_start', string='Entrada', readonly=True,
    )
    date_end = fields.Datetime(
        related='productivity_id.date_end', string='Salida', readonly=True,
    )
    abierto = fields.Boolean(
        string='Fichaje abierto (sin salida)', compute='_compute_abierto',
    )
    workorder_origen_id = fields.Many2one(
        'mrp.workorder', string='Fase actual', readonly=True,
    )
    production_origen_id = fields.Many2one(
        'mrp.production', string='OF actual', readonly=True,
    )

    production_id = fields.Many2one(
        'mrp.production', string='Nueva OF',
        domain="[('state', 'not in', ('cancel',))]",
    )
    workorder_id = fields.Many2one(
        'mrp.workorder', string='Nueva fase',
        domain="[('production_id', '=', production_id), ('state', 'not in', ('cancel',))]",
    )
    motivo = fields.Char(
        string='Motivo (opcional)',
        help='Se guarda en el histórico del fichaje. No es obligatorio.',
    )

    @api.depends('productivity_id.date_end')
    def _compute_abierto(self):
        for w in self:
            w.abierto = bool(w.productivity_id) and not w.productivity_id.date_end

    @api.onchange('production_id')
    def _onchange_production_id(self):
        # Al cambiar de OF, limpiar la fase si ya no pertenece a la nueva OF.
        if self.workorder_id and self.workorder_id.production_id != self.production_id:
            self.workorder_id = False

    def action_aplicar(self):
        self.ensure_one()
        prod = self.productivity_id
        wo = self.workorder_id
        if not wo:
            raise UserError(_("Elige la fase (orden de trabajo) de destino."))
        if wo == self.workorder_origen_id:
            raise UserError(_("El fichaje ya está en esa fase. Elige otra distinta."))

        origen_txt = "%s / %s" % (
            self.workorder_origen_id.production_id.name or '?',
            self.workorder_origen_id.name or '?',
        )
        destino_txt = "%s / %s" % (
            wo.production_id.name or '?', wo.name or '?',
        )

        vals = {
            'workorder_id': wo.id,
            'workcenter_id': wo.workcenter_id.id,
        }
        # Reutiliza los campos de trazabilidad que ya existen (histórico).
        if 'apunts_modificado_manual' in prod._fields:
            vals.update({
                'apunts_modificado_manual': True,
                'apunts_modificado_por_id': self.env.user.id,
                'apunts_modificado_fecha': fields.Datetime.now(),
            })
            if self.motivo and 'apunts_motivo_correccion' in prod._fields:
                vals['apunts_motivo_correccion'] = self.motivo
        prod.write(vals)

        # Si el fichaje estaba abierto, reflejar al operario como trabajando
        # en la nueva fase (y quitarlo de la anterior) para que la vista taller
        # y el "quién está fichado" queden coherentes.
        if not prod.date_end and prod.employee_id:
            emp = prod.employee_id
            if 'employee_ids' in wo._fields:
                if emp in self.workorder_origen_id.employee_ids:
                    self.workorder_origen_id.employee_ids = [(3, emp.id)]
                if emp not in wo.employee_ids:
                    wo.employee_ids = [(4, emp.id)]

        cuerpo = _(
            "🔧 Fichaje reasignado por %(user)s: %(origen)s → %(destino)s "
            "(entrada %(ini)s%(fin)s)%(motivo)s."
        ) % {
            'user': self.env.user.name,
            'origen': origen_txt,
            'destino': destino_txt,
            'ini': fields.Datetime.to_string(prod.date_start),
            'fin': (", salida %s" % fields.Datetime.to_string(prod.date_end)) if prod.date_end else ", sin salida (abierto)",
            'motivo': (_("\nMotivo: %s") % self.motivo) if self.motivo else '',
        }
        # Anotar en las dos OFs implicadas para trazabilidad
        self.workorder_origen_id.production_id.message_post(body=cuerpo)
        if wo.production_id != self.workorder_origen_id.production_id:
            wo.production_id.message_post(body=cuerpo)
        return {'type': 'ir.actions.act_window_close'}
