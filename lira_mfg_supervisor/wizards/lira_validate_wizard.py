from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.lira_mfg_supervisor.models.lira_refabricacion import MOTIVOS_REFABRICACION


class LiraValidateWizard(models.TransientModel):
    _name = 'lira.validate.wizard'
    _description = 'Wizard validación/rechazo supervisor'

    workorder_id    = fields.Many2one('mrp.workorder', required=True, readonly=True)
    production_name = fields.Char(related='workorder_id.lira_production_seq', readonly=True)
    product_name    = fields.Char(related='workorder_id.production_id.product_id.display_name', readonly=True)
    workorder_name  = fields.Char(related='workorder_id.name', readonly=True)
    # Operarios que ficharon en la fase. Se leen de los registros de
    # productividad (time_ids), que persisten aunque ya se hayan desfichado;
    # NO de employee_ids (fichados en vivo), que al validar ya está vacío.
    # Se rellenan en default_get (al abrir el wizard), no por compute: el
    # compute no se dispara de forma fiable al abrir el transitorio desde la
    # acción (workorder_id es readonly y llega por contexto).
    operator_names  = fields.Char(string='Operarios de la fase', readonly=True)

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

    # Motivo de calidad — obligatorio al enviar piezas a retrabajo/reposición.
    motivo = fields.Selection(
        MOTIVOS_REFABRICACION, string='Motivo de la rectificación')
    # Operarios implicados (los que ficharon en la fase). Pueden ser varios:
    # se rellenan automáticamente y el supervisor puede ajustarlos. El
    # responsable de validación decide a quién atribuir la rectificación.
    # Campo editable: se rellena por defecto (default_get) con todos los
    # operarios de la fase; el supervisor puede quitar a quien no corresponda.
    employee_responsable_ids = fields.Many2many(
        'hr.employee', 'lira_validate_wizard_emp_rel', 'wizard_id', 'employee_id',
        string='Operarios implicados',
        domain="[('id', 'in', empleados_disponibles_ids)]")
    # Solo para el dominio del campo de arriba (operarios seleccionables).
    empleados_disponibles_ids = fields.Many2many(
        'hr.employee', 'lira_validate_wizard_emp_disp_rel', 'wizard_id', 'employee_id')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        wo_id = res.get('workorder_id') or self.env.context.get('default_workorder_id')
        if wo_id:
            # sudo: el supervisor puede no tener lectura directa sobre la
            # productividad; aun así debemos poder listar los operarios.
            wo = self.env['mrp.workorder'].sudo().browse(wo_id)
            emps = wo.time_ids.filtered('employee_id').employee_id
            res['empleados_disponibles_ids'] = [(6, 0, emps.ids)]
            res['employee_responsable_ids'] = [(6, 0, emps.ids)]
            res['operator_names'] = ', '.join(emps.mapped('name'))
        return res

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
        if no_val > 0 and not self.motivo:
            raise ValidationError(
                "Indica el motivo de la rectificación (Retrabajo/Reposición)."
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
            compras_info = ""
            if self.accion_no_validada == 'reposicion':
                wo.lira_qty_reposicion = (wo.lira_qty_reposicion or 0.0) + no_val
                etiqueta = "REPOSICIÓN (desechar y volver a fabricar)"
                # Operativa real: para rehacer las piezas desechadas hay que
                # COMPRAR material nuevo. Creamos pedido(s) de compra en borrador
                # con los componentes proporcionales, vinculados a la OF. El coste
                # real lo coge el WIP del importe de esas compras (no se estima),
                # así que NO se duplica.
                pos, sin_prov = self._crear_compra_reposicion(prod, no_val)
                if pos:
                    compras_info = " Compra(s) de reposición creada(s) (borrador): %s." % ', '.join(pos.mapped('name'))
                if sin_prov:
                    compras_info += " ⚠ Sin proveedor (añádelos a mano): %s." % ', '.join(sin_prov)
            else:
                wo.lira_qty_retrabajo = (wo.lira_qty_retrabajo or 0.0) + no_val
                etiqueta = "RETRABAJO (reprocesar las mismas piezas)"
                # Retrabajo: NO consume material nuevo (se reaprovecha la pieza).
                # El coste sube solo por la mano de obra del reproceso (fichaje).

            motivo_label = dict(MOTIVOS_REFABRICACION).get(self.motivo, self.motivo)
            # Línea de trazabilidad: qué operarios, cuántas piezas, acción y motivo.
            self.env['lira.refabricacion.linea'].create({
                'workorder_id': wo.id,
                'production_id': prod.id,
                'employee_ids': [(6, 0, self.employee_responsable_ids.ids)],
                'qty': no_val,
                'accion': self.accion_no_validada,
                'motivo': self.motivo,
                'supervisor_id': self.env.user.id,
            })
            wo.production_id.message_post(body=(
                "Supervisor %(user)s — fase %(wo)s: %(val)s uds validadas, "
                "%(no)s uds NO validadas → <b>%(et)s</b>. Motivo: <b>%(mot)s</b>. "
                "Operarios: %(emp)s. Las no validadas vuelven a producción para completarse."
                "%(compras)s"
            ) % {
                'user': self.env.user.name, 'wo': wo.name,
                'val': qty, 'no': no_val, 'et': etiqueta,
                'mot': motivo_label,
                'emp': ', '.join(self.employee_responsable_ids.mapped('name')) or '—',
                'compras': compras_info,
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

    def _crear_compra_reposicion(self, prod, no_val):
        """Crea pedido(s) de compra en BORRADOR para reponer `no_val` piezas:
        componentes de la OF (move_raw) en cantidad proporcional, agrupados por
        proveedor preferido, vinculados a la OF (fabricacion) y marcados como
        reposición (apunts_es_reposicion). El WIP suma su importe como MP extra.

        Devuelve (purchase.orders creados, [nombres de productos sin proveedor]).
        Se crea con sudo: el supervisor puede no tener permisos de compras."""
        POrders = self.env['purchase.order'].sudo()
        if not prod.product_qty:
            return POrders.browse(), []
        ratio = no_val / prod.product_qty
        por_proveedor = {}   # partner_id -> [líneas]
        sin_proveedor = []
        for m in prod.move_raw_ids:
            if m.state == 'cancel' or not m.product_id:
                continue
            qty = (m.product_qty or 0.0) * ratio
            if qty <= 0:
                continue
            seller = m.product_id.seller_ids[:1]
            if not seller or not seller.partner_id:
                sin_proveedor.append(m.product_id.display_name)
                continue
            por_proveedor.setdefault(seller.partner_id.id, []).append((0, 0, {
                'product_id': m.product_id.id,
                'product_qty': qty,
                'product_uom': m.product_uom.id or m.product_id.uom_po_id.id,
                'price_unit': seller.price or m.product_id.standard_price or 0.0,
                'name': m.product_id.display_name,
                'date_planned': fields.Datetime.now(),
                'fabricacion': prod.id,
                'apunts_es_reposicion': True,
            }))
        pos = POrders.browse()
        for partner_id, lineas in por_proveedor.items():
            pos |= POrders.create({
                'partner_id': partner_id,
                'origin': '%s (reposición)' % (prod.name or ''),
                'order_line': lineas,
            })
        return pos, sin_proveedor

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
