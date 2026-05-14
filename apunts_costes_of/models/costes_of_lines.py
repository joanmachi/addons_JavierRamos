from odoo import models, fields, api


class ApuntsCostesOfMaterialLine(models.TransientModel):
    """Una fila por componente de material en la vista Costes OF.
    TransientModel: se regenera con _recompute_costes_lines() en cada apertura.
    """
    _name = 'apunts.costes.of.material.line'
    _description = 'Linea de material en vista Costes OF'
    _order = 'cost_total desc, id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(
        'res.currency', related='production_id.currency_id', readonly=True,
        help='Moneda para formateo monetario (heredada de la company de la OF).',
    )
    move_id = fields.Many2one('stock.move', readonly=True,
                              help='Movimiento de stock origen de este consumo (stock.move).')
    product_id = fields.Many2one('product.product', readonly=True,
                                 help='Componente fisico que se consume.')
    product_name = fields.Char(readonly=True,
                               help='Nombre del componente — copia textual de product.product.display_name.')
    uom_id = fields.Many2one('uom.uom', readonly=True,
                             help='Unidad de medida del componente (uom.uom del move).')

    qty_needed = fields.Float('Necesario', digits=(16, 3), readonly=True,
                              help='Cantidad teorica que necesita la OF (stock.move.product_uom_qty).')
    qty_consumed = fields.Float('Consumido', digits=(16, 3), readonly=True,
                                help='Cantidad ya consumida (stock.move.quantity con state=done).')
    qty_reserved = fields.Float('Reservado', digits=(16, 3), readonly=True,
                                help='Cantidad reservada en stock (state=assigned o partially_available).')
    qty_in_transit = fields.Float('De camino', digits=(16, 3), readonly=True,
                                  help='Cantidad pendiente de recibir vinculada a esta OF via procurement_group_id.')
    qty_missing = fields.Float('Falta sin PO', digits=(16, 3), readonly=True,
                               help='Diferencia: necesario - consumido - reservado - de camino. Si > 0, hay que crear PO.')

    standard_price = fields.Monetary('Coste estandar', currency_field='currency_id', readonly=True,
                                     help='product.product.standard_price del producto. Si vale 0, el coste consumido sale 0 y aparece alerta.')
    cost_total = fields.Monetary('Coste consumido', currency_field='currency_id', readonly=True,
                                 help='qty_consumed x standard_price. Coste real ya gastado en este componente.')
    cost_pending = fields.Monetary('Coste pendiente', currency_field='currency_id', readonly=True,
                                   help='(reservado + de camino + falta) x standard_price. Coste estimado que aun queda por imputar.')
    cost_total_needed = fields.Monetary('Coste (€)', currency_field='currency_id', readonly=True,
                                        help='qty_needed x standard_price. Coste total esperado para este componente si se consume la cantidad completa segun la OF.')

    state = fields.Selection([
        ('green', 'OK'),
        ('amber', 'Atencion'),
        ('red', 'Falta'),
    ], readonly=True,
       help='Verde = consumido completo; Ambar = en curso; Rojo = falta sin PO.')

    purchase_order_id = fields.Many2one('purchase.order', readonly=True,
                                        help='PO origen (si una sola la aprovisiona via procurement_group_id).')

    # Hito 4 - trazabilidad backward
    seller_partner_id = fields.Many2one('res.partner', readonly=True,
                                        string='Proveedor preferido',
                                        help='Primer proveedor de product.product.seller_ids. Sirve para auditoria backward.')
    seller_partner_name = fields.Char('Proveedor', readonly=True,
                                      help='Nombre del proveedor preferido. Util en list views sin clicar.')
    avg_purchase_price = fields.Monetary('Coste promedio compra (EUR/u)', currency_field='currency_id', readonly=True,
                                         help='Promedio ponderado: SUM(POL.price_unit x qty_received) / SUM(qty_received) en POs purchase/done. Comparalo con standard_price para detectar desviaciones de coste real vs registrado.')
    lot_ids_summary = fields.Char('Lotes consumidos', readonly=True,
                                  help='Lotes (stock.lot) que aportaron este consumo. Trazabilidad backward al lote del proveedor.')
    lot_id = fields.Many2one('stock.lot', readonly=True,
                             help='Lote unico si solo hay uno; sino vacio (ver lot_ids_summary).')

    def action_open_seller(self):
        self.ensure_one()
        if not self.seller_partner_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.seller_partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_lot(self):
        self.ensure_one()
        if not self.lot_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'res_id': self.lot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_purchase(self):
        self.ensure_one()
        if not self.purchase_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_po_for_missing(self):
        """Crea PO borrador con la cantidad faltante. Reusa proveedor preferido del producto."""
        self.ensure_one()
        if self.qty_missing <= 0 or not self.product_id:
            return False
        seller = self.product_id.seller_ids[:1]
        partner = seller.partner_id if seller else False
        if not partner:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Falta proveedor',
                    'message': f'El producto {self.product_id.display_name} no tiene proveedor asociado. Anyade uno antes de crear PO.',
                    'sticky': True,
                    'type': 'warning',
                },
            }
        po_vals = {
            'partner_id': partner.id,
            'origin': self.production_id.name,
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_qty': self.qty_missing,
                'product_uom': self.uom_id.id or self.product_id.uom_po_id.id,
                'price_unit': seller.price if seller else self.standard_price or 0.0,
                'name': self.product_id.display_name,
                'date_planned': fields.Datetime.now(),
            })],
        }
        po = self.env['purchase.order'].create(po_vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ApuntsCostesOfLaborLine(models.TransientModel):
    """Una fila por workorder en la vista Costes OF (seccion 2)."""
    _name = 'apunts.costes.of.labor.line'
    _description = 'Linea de mano de obra en vista Costes OF'
    _order = 'workorder_sequence, id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(
        'res.currency', related='production_id.currency_id', readonly=True,
        help='Moneda para formateo monetario (heredada de la company de la OF).',
    )
    workorder_id = fields.Many2one('mrp.workorder', readonly=True,
                                   help='Orden de trabajo (mrp.workorder) origen.')
    workorder_sequence = fields.Integer(readonly=True)
    workorder_name = fields.Char(readonly=True,
                                 help='Nombre/codigo de la OT. Sirve para identificar en listados.')
    workcenter_id = fields.Many2one('mrp.workcenter', readonly=True,
                                    help='Centro de trabajo donde se ejecuta la OT.')
    workcenter_name = fields.Char(readonly=True)
    operation_id = fields.Many2one('mrp.routing.workcenter', readonly=True,
                                   help='Operacion del routing/BoM asociada.')

    hours_planned = fields.Float('Horas plan', digits=(16, 2), readonly=True,
                                 help='Horas teoricas (mrp.workorder.duration_expected/60).')
    hours_real = fields.Float('Horas real', digits=(16, 2), readonly=True,
                              help='Horas reales imputadas (mrp.workorder.duration/60). Suma de productivity entries.')
    progress_pct = fields.Float('% avance', digits=(16, 1), readonly=True,
                                help='hours_real / hours_planned x 100. Si supera 115%, alerta de OT desbordada.')

    cost_workcenter = fields.Monetary('Coste centro/maquina', currency_field='currency_id', readonly=True,
                                      help='SUM(productivity.duration/60 x mrp.workcenter.costs_hour). Coste de maquina por minutos imputados.')
    cost_employee = fields.Monetary('Coste empleado', currency_field='currency_id', readonly=True,
                                    help='SUM(productivity.duration/60 x hr.employee.hourly_cost). Coste laboral imputado a esta OT.')
    cost_total = fields.Monetary('Coste total', currency_field='currency_id', readonly=True,
                                 help='cost_workcenter + cost_employee. Coste real total de esta OT.')

    employees_count = fields.Integer('Empleados', readonly=True)
    employees_summary = fields.Char('Empleados imputados', readonly=True,
                                    help='Hasta 4 nombres distintos de empleados con productivity entries en esta OT.')

    state = fields.Selection([
        ('green', 'OK'),
        ('amber', 'Atencion'),
        ('red', 'Desbordada'),
        ('pending', 'Pendiente'),
    ], readonly=True)

    workorder_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('waiting', 'En espera'),
        ('ready', 'Listo'),
        ('progress', 'En progreso'),
        ('done', 'Hecho'),
        ('cancel', 'Cancelado'),
    ], readonly=True)

    def action_open_workorder(self):
        self.ensure_one()
        if not self.workorder_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'res_id': self.workorder_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ApuntsCostesOfAttendanceLine(models.TransientModel):
    """Una fila por (empleado x dia x OT) en la vista Costes OF (seccion 2-bis).
    Hito 3: hojas de asistencia desglosadas. Drill-down a hr.employee, productivity, workorder.
    """
    _name = 'apunts.costes.of.attendance.line'
    _description = 'Linea de asistencia empleado x dia en vista Costes OF'
    _order = 'day_date, employee_name, workorder_name, id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(
        'res.currency', related='production_id.currency_id', readonly=True,
        help='Moneda para formateo monetario.',
    )
    workorder_id = fields.Many2one('mrp.workorder', readonly=True,
                                   help='Orden de trabajo (mrp.workorder) en la que el empleado imputo horas.')
    workorder_name = fields.Char(readonly=True)
    workcenter_id = fields.Many2one('mrp.workcenter', readonly=True,
                                    help='Centro de trabajo (mrp.workcenter) en el que se imputo.')
    workcenter_name = fields.Char(readonly=True)
    employee_id = fields.Many2one('hr.employee', readonly=True,
                                  help='Empleado (hr.employee) que imputo las horas. Puede estar vacio si la productivity entry no tenia employee_id (imputacion solo a centro).')
    employee_name = fields.Char(readonly=True)

    day_date = fields.Date('Dia', readonly=True,
                           help='Fecha de la imputacion (DATE de productivity.date_start).')
    day_label = fields.Char('Dia (texto)', readonly=True)
    hours = fields.Float('Horas', digits=(16, 2), readonly=True,
                         help='SUM(productivity.duration)/60 agregadas por (empleado x dia x OT).')
    hourly_cost = fields.Monetary('Coste/hora empleado', currency_field='currency_id', readonly=True,
                                  help='hr.employee.hourly_cost del empleado al momento del calculo. Si vale 0, fila en estado amber.')
    cost_total = fields.Monetary('Coste empleado', currency_field='currency_id', readonly=True,
                                 help='hours x hourly_cost. Coste laboral real de esta imputacion.')

    state = fields.Selection([
        ('green', 'OK'),
        ('amber', 'Sin coste'),
        ('blue', 'Sin empleado'),
    ], readonly=True,
       help='Verde = empleado con coste/hora; Ambar = empleado sin hourly_cost configurado (master data); Azul = imputacion sin employee_id.')

    def action_open_employee(self):
        self.ensure_one()
        if not self.employee_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': self.employee_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_workorder(self):
        self.ensure_one()
        if not self.workorder_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'res_id': self.workorder_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_day_productivity(self):
        """Drill al dia: lista de productivity entries del empleado en esa fecha (cualquier OF)."""
        self.ensure_one()
        if not self.employee_id or not self.day_date:
            return False
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('date_start', '>=', fields.Datetime.to_datetime(self.day_date)),
            ('date_start', '<', fields.Datetime.to_datetime(
                fields.Date.add(self.day_date, days=1))),
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': f'Imputaciones {self.employee_name} - {self.day_label}',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'list,pivot',
            'domain': domain,
            'target': 'current',
        }


class ApuntsCostesOfFinishedLine(models.TransientModel):
    """Una fila por movimiento de producto terminado de la OF (seccion 6 - trazabilidad forward).
    Hito 4: SO destino + cliente + albaran + lote producido + margen comercial.
    """
    _name = 'apunts.costes.of.finished.line'
    _description = 'Linea de producto terminado en vista Costes OF'
    _order = 'id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(
        'res.currency', related='production_id.currency_id', readonly=True,
        help='Moneda para formateo monetario.',
    )
    move_id = fields.Many2one('stock.move', readonly=True,
                              help='Movimiento de stock terminado (stock.move) origen de esta fila.')
    product_id = fields.Many2one('product.product', readonly=True,
                                 help='Producto terminado de la OF.')
    product_name = fields.Char(readonly=True)
    qty_produced = fields.Float('Cantidad producida', digits=(16, 3), readonly=True,
                                help='Cantidad efectivamente producida (stock.move.quantity si done; sino product_uom_qty).')
    uom_id = fields.Many2one('uom.uom', readonly=True,
                             help='Unidad de medida del producto terminado.')

    lot_id = fields.Many2one('stock.lot', readonly=True,
                             help='Lote producido (stock.lot) — primer lote de move_line_ids si lo hay.')
    lot_name = fields.Char('Lote', readonly=True,
                           help='Nombre del lote o lista de lotes si hay varios.')

    picking_id = fields.Many2one('stock.picking', readonly=True,
                                 help='Albaran de salida al cliente (stock.picking outgoing) localizado siguiendo move_dest_ids.')
    picking_name = fields.Char('Albaran salida', readonly=True)
    picking_state = fields.Char(readonly=True,
                                help='Estado del albaran (draft / waiting / confirmed / assigned / done / cancel).')
    delivery_date = fields.Date('Entrega comprometida', readonly=True,
                                help='Fecha de entrega prevista (stock.picking.scheduled_date).')

    sale_order_id = fields.Many2one('sale.order', readonly=True,
                                    help='Pedido cliente (sale.order) vinculado.')
    sale_order_name = fields.Char('Pedido cliente', readonly=True)
    sale_partner_id = fields.Many2one('res.partner', readonly=True,
                                      help='Cliente final del pedido (res.partner).')
    sale_partner_name = fields.Char('Cliente', readonly=True)
    sale_price_unit = fields.Monetary('Precio venta unit.', currency_field='currency_id', readonly=True,
                                      help='Precio unitario de la sale.order.line vinculada al producto. Sirve para calcular ingreso real, no el list_price teorico.')
    sale_revenue = fields.Monetary('Ingreso total', currency_field='currency_id', readonly=True,
                                   help='qty_produced x sale_price_unit. Lo que cobramos por esta produccion.')

    cost_real_total = fields.Monetary('Coste real OF', currency_field='currency_id', readonly=True,
                                      help='Coste real total imputado a la OF (material + mano de obra + operacion). Si la OF produce varios items, este coste se imputa al conjunto.')
    margin = fields.Monetary('Margen comercial', currency_field='currency_id', readonly=True,
                             help='Ingreso - coste real. Si negativo, perdemos dinero al fabricar este producto.')
    margin_pct = fields.Float('Margen %', digits=(16, 1), readonly=True,
                              help='margin / sale_revenue x 100. Verde > 20%; Ambar 0-20%; Rojo si negativo.')

    state = fields.Selection([
        ('green', 'Margen OK'),
        ('amber', 'Margen ajustado'),
        ('red', 'Margen NEGATIVO'),
        ('blue', 'Sin SO vinculada (stock)'),
    ], readonly=True,
       help='Verde = margen >= 20%; Ambar = entre 0% y 20%; Rojo = negativo; Azul = OF a stock sin pedido cliente.')

    margin_explanation = fields.Char('Explicacion margen', readonly=True,
                                     help='Frase autoexplicativa estilo "Vendi a X EUR, me cuesta Y EUR. Margen Z EUR (W%)" — pensada para Javi, sin requerir leer columnas separadas.')

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_lot(self):
        self.ensure_one()
        if not self.lot_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'res_id': self.lot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_picking(self):
        self.ensure_one()
        if not self.picking_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_partner(self):
        self.ensure_one()
        if not self.sale_partner_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.sale_partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ApuntsCostesOfAlert(models.TransientModel):
    """Una fila por alerta activa en la vista Costes OF (seccion 5)."""
    _name = 'apunts.costes.of.alert'
    _description = 'Alerta activa en vista Costes OF'
    _order = 'severity desc, id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    severity = fields.Selection([
        ('red', 'Critica'),
        ('amber', 'Atencion'),
        ('blue', 'Informativa'),
    ], required=True)
    message = fields.Char(readonly=True)
    related_workorder_id = fields.Many2one('mrp.workorder', readonly=True)
    related_product_id = fields.Many2one('product.product', readonly=True)
    related_sale_order_id = fields.Many2one('sale.order', readonly=True)

    def action_open_related(self):
        self.ensure_one()
        if self.related_workorder_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.workorder',
                'res_id': self.related_workorder_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if self.related_sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.related_sale_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if self.related_product_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'res_id': self.related_product_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False
