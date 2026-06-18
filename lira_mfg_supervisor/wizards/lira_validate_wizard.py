from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LiraValidateWizard(models.TransientModel):
    _name = 'lira.validate.wizard'
    _description = 'Wizard validación/rechazo supervisor'

    workorder_id    = fields.Many2one('mrp.workorder', required=True, readonly=True)
    production_name = fields.Char(related='workorder_id.lira_production_seq', readonly=True)
    product_name    = fields.Char(related='workorder_id.production_id.product_id.display_name', readonly=True)
    workorder_name  = fields.Char(related='workorder_id.name', readonly=True)
    operator_names  = fields.Char(related='workorder_id.texto_fichados', readonly=True)

    # Float normal con default desde contexto — evita el problema de related en TransientModel
    qty_pending     = fields.Float(string='Solicitado por operario', readonly=True, digits=(16, 2))
    qty_to_validate = fields.Float(string='Cantidad a validar', digits=(16, 2))

    wizard_mode     = fields.Selection([
        ('validate', 'Validar'),
        ('reject',   'Rechazar'),
    ], default='validate', required=True)
    rejection_note  = fields.Char(string='Motivo del rechazo')

    # Piezas que el supervisor NO valida (entregadas − validadas): hay que
    # decidir si se reprocesan (retrabajo) o se desechan y rehacen (reposición).
    qty_no_validada = fields.Float(
        string='Piezas no validadas',
        compute='_compute_qty_no_validada',
        digits=(16, 2),
    )
    accion_no_validada = fields.Selection([
        ('retrabajo', 'Retrabajo — reprocesar las mismas piezas (sin material nuevo)'),
        ('reposicion', 'Reposición — desechar y volver a fabricar (material nuevo)'),
    ], string='¿Qué hacer con las no validadas?')

    @api.depends('qty_pending', 'qty_to_validate')
    def _compute_qty_no_validada(self):
        for w in self:
            w.qty_no_validada = max((w.qty_pending or 0.0) - (w.qty_to_validate or 0.0), 0.0)

    def action_validate(self):
        self.ensure_one()
        wo = self.workorder_id
        qty = self.qty_to_validate or 0.0
        no_val = self.qty_no_validada

        if qty < 0:
            raise ValidationError("La cantidad a validar no puede ser negativa.")
        if qty > wo.qty_ready_to_validate:
            raise ValidationError(
                f"No puedes validar más de {wo.qty_ready_to_validate} unidades (cantidad entregada por el operario)."
            )
        if qty <= 0 and no_val <= 0:
            raise ValidationError("Indica una cantidad a validar.")
        if no_val > 0 and not self.accion_no_validada:
            raise ValidationError(
                "Hay %s piezas no validadas: indica si van a Retrabajo o Reposición." % no_val
            )

        # El write de qty_validated dispara el auto-trigger de
        # apunts_barcode_workorder (cierre OF + back-order con transferencia
        # de excedentes) si esta WO es la ultima fase. Por eso NO hace falta
        # gestionar qty_producing aqui: el auto-trigger lo set correctamente.
        #
        # Las piezas NO validadas se sacan también de "listas para validar":
        # al no quedar validadas, prev_validated_qty hace que vuelvan a contar
        # como "por hacer" y el operario las rehace (reposición) o reprocesa
        # (retrabajo). La diferencia entre ambas es solo el registro/coste:
        # reposición = se desecha y se gasta material nuevo; retrabajo = se
        # reutiliza la pieza.
        vals = {
            'qty_ready_to_validate': wo.qty_ready_to_validate - qty - no_val,
            'lira_validated_by': self.env.user.id,
            'lira_validated_date': fields.Datetime.now(),
            'lira_supervisor_note': False,
        }
        if qty > 0:
            vals['qty_validated'] = wo.qty_validated + qty
        wo.write(vals)

        if no_val > 0:
            prod = wo.production_id
            if self.accion_no_validada == 'reposicion':
                wo.lira_qty_reposicion = (wo.lira_qty_reposicion or 0.0) + no_val
                etiqueta = "REPOSICIÓN (desechar y volver a fabricar)"
                # Material extra: se consume material nuevo para rehacer las
                # piezas desechadas. Proporcional al consumo ya registrado:
                #   extra (€) = material_base_OF × (piezas_repuestas / entregadas)
                # Se acumula en la OF y el módulo de coste lo suma al MP real.
                if 'apunts_mat_reposicion_extra' in prod._fields and self.qty_pending:
                    mat_base = prod._apunts_mp_total_real(prod)
                    extra = mat_base * (no_val / self.qty_pending)
                    if extra:
                        prod.apunts_mat_reposicion_extra = (
                            prod.apunts_mat_reposicion_extra or 0.0
                        ) + extra
            else:
                wo.lira_qty_retrabajo = (wo.lira_qty_retrabajo or 0.0) + no_val
                etiqueta = "RETRABAJO (reprocesar las mismas piezas)"
                # Retrabajo: NO consume material nuevo (se reaprovecha la pieza).
                # El coste sube solo por la mano de obra del reproceso (fichaje).
            wo.production_id.message_post(body=(
                "Supervisor %(user)s — fase %(wo)s: %(val)s uds validadas, "
                "%(no)s uds NO validadas → <b>%(et)s</b>. "
                "Las no validadas vuelven a producción para completarse."
            ) % {
                'user': self.env.user.name, 'wo': wo.name,
                'val': qty, 'no': no_val, 'et': etiqueta,
            })

        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'mrp.production'),
            ('res_id', '=', wo.production_id.id),
            ('summary', '=', 'Orden de trabajo actualizada'),
        ])
        if activities:
            activities.action_feedback(
                feedback=f"Validado {qty} uds. en '{wo.name}' por {self.env.user.name}"
            )

        self.env.user._bus_send("barcode_refresh_requested", {'production_id': wo.production_id.id})
        return {'type': 'ir.actions.act_window_close'}

    def action_reject(self):
        self.ensure_one()
        if not self.rejection_note:
            raise ValidationError("Debes indicar el motivo del rechazo.")

        wo = self.workorder_id
        wo.write({
            'qty_ready_to_validate': 0,
            'lira_date_ready': False,
            'lira_supervisor_note': self.rejection_note,
            'lira_rejection_date': fields.Datetime.now(),
        })

        self.env.user._bus_send("barcode_refresh_requested", {'production_id': wo.production_id.id})
        return {'type': 'ir.actions.act_window_close'}
