from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('apunts_costes_of', 'post_install', '-at_install')
class TestApuntsCostesOf(TransactionCase):
    """Tests minimos del modulo apunts_costes_of.

    Cubre:
    - El compute de KPIs no rompe sobre OFs sin BoM ni sin workorders.
    - El compute es estable: llamarlo dos veces da el mismo resultado.
    - La regeneracion de lineas crea correctamente los 5 modelos auxiliares.
    - La accion smart button devuelve un act_window valido.
    - Los drill-down devuelven act_window con dominio correcto.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Producto terminado y MP minimos
        cls.product_pt = cls.env['product.product'].create({
            'name': 'Test Producto Terminado',
            'type': 'consu',
            'is_storable': True,
            'standard_price': 100.0,
            'list_price': 200.0,
        })
        cls.product_mp = cls.env['product.product'].create({
            'name': 'Test MP',
            'type': 'consu',
            'is_storable': True,
            'standard_price': 5.0,
        })
        # BoM minimo
        cls.bom = cls.env['mrp.bom'].create({
            'product_id': cls.product_pt.id,
            'product_tmpl_id': cls.product_pt.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [(0, 0, {
                'product_id': cls.product_mp.id,
                'product_qty': 2.0,
            })],
        })
        # OF minima sin workorders (sin operations)
        cls.mo = cls.env['mrp.production'].create({
            'product_id': cls.product_pt.id,
            'product_qty': 5.0,
            'bom_id': cls.bom.id,
        })

    def test_01_compute_kpis_no_explode(self):
        """El compute KPIs no debe lanzar excepciones sobre OF en draft sin workorders."""
        self.mo._do_compute_apunts_costs()
        self.assertEqual(self.mo.apunts_total_cost_real, 0.0,
                         'OF en draft sin moves done debe tener coste real 0.')
        self.assertGreater(self.mo.apunts_material_cost_planned, 0.0,
                           'OF con BoM debe tener material planificado > 0.')
        self.assertEqual(self.mo.apunts_material_cost_planned, 50.0,
                         '5 unidades x 2 MP/u x 5 EUR/u = 50 EUR teorico material.')

    def test_02_compute_idempotent(self):
        """Llamar al compute dos veces produce el mismo resultado."""
        self.mo._do_compute_apunts_costs()
        first_total = self.mo.apunts_total_cost_planned
        first_traffic = self.mo.apunts_traffic_light
        self.mo._do_compute_apunts_costs()
        self.assertEqual(self.mo.apunts_total_cost_planned, first_total)
        self.assertEqual(self.mo.apunts_traffic_light, first_traffic)

    def test_03_regenerate_lines_creates_records(self):
        """_apunts_regenerate_lines debe crear registros en los 5 modelos auxiliares
        (al menos sin errores; el numero exacto depende del estado de la OF).
        """
        # Confirmar la OF para que tenga move_raw_ids creados
        self.mo.action_confirm()
        self.mo._apunts_regenerate_lines()
        # Material lines: una por cada move_raw_ids
        self.assertEqual(len(self.mo.apunts_material_line_ids), 1,
                         'Debe haber 1 material line (un componente en BoM).')
        material = self.mo.apunts_material_line_ids[0]
        self.assertEqual(material.product_id.id, self.product_mp.id)
        self.assertAlmostEqual(material.qty_needed, 10.0, places=1,
                               msg='5 unidades x 2 MP/u = 10 unidades necesarias.')
        # Sin workorders: labor=0, attendance=0, finished=1 (move terminado),
        # alerts puede tener varias.
        self.assertEqual(len(self.mo.apunts_labor_line_ids), 0,
                         'Sin operations en BoM, no hay workorders.')
        self.assertEqual(len(self.mo.apunts_attendance_line_ids), 0,
                         'Sin productivity entries, no hay attendance.')
        # finished_line: debe haber al menos uno (el move del producto terminado)
        self.assertGreaterEqual(len(self.mo.apunts_finished_line_ids), 1)

    def test_04_smart_button_action(self):
        """action_apunts_open_costes devuelve un act_window apuntando al view costes."""
        action = self.mo.action_apunts_open_costes()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'mrp.production')
        self.assertEqual(action['res_id'], self.mo.id)
        self.assertEqual(action['view_mode'], 'form')
        self.assertTrue(action.get('view_id'))

    def test_05_drill_actions_return_valid_domain(self):
        """Los drill-down devuelven act_windows con domain bien formado."""
        drill_mat = self.mo.action_apunts_drill_material()
        self.assertEqual(drill_mat['res_model'], 'stock.move')
        self.assertIn(('raw_material_production_id', '=', self.mo.id), drill_mat['domain'])

        drill_op = self.mo.action_apunts_drill_operation()
        self.assertEqual(drill_op['res_model'], 'mrp.workorder')
        self.assertIn(('production_id', '=', self.mo.id), drill_op['domain'])

        drill_att = self.mo.action_apunts_drill_attendance()
        self.assertEqual(drill_att['res_model'], 'mrp.workcenter.productivity')

        drill_fin = self.mo.action_apunts_drill_finished()
        self.assertEqual(drill_fin['res_model'], 'stock.move')
        self.assertIn(('production_id', '=', self.mo.id), drill_fin['domain'])

    def test_06_traffic_light_values(self):
        """El semaforo solo devuelve valores validos del Selection."""
        self.mo._do_compute_apunts_costs()
        self.assertIn(self.mo.apunts_traffic_light, ('green', 'amber', 'red'))

    def test_07_revenue_zero_without_sale(self):
        """OF sin sale_id debe tener revenue=0 y margen=0."""
        self.mo._do_compute_apunts_costs()
        self.assertEqual(self.mo.apunts_revenue_total, 0.0)
        self.assertEqual(self.mo.apunts_margin_total, 0.0)

    # ============================================================
    # HITO 11 - Soporte campo Studio sale.order
    # ============================================================

    def test_08_studio_field_auto_detect_robust(self):
        """El helper auto-detecta y persiste el resultado en ICP, sea o no haya campo Studio.

        Test robusto: en JR existe x_studio_venta -> devuelve ese nombre.
        En BDs sin campo Studio -> devuelve '' y persiste '__none__'.
        En cualquier caso, el resultado debe coincidir con campos m2o(sale.order) reales.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('apunts_costes_of.studio_sale_field', '')
        result = self.env['mrp.production']._apunts_get_studio_sale_field()
        cached = ICP.get_param('apunts_costes_of.studio_sale_field') or ''
        # Tras el lookup, ICP debe tener algo (campo encontrado o '__none__').
        self.assertTrue(cached,
                        'El helper debe persistir SIEMPRE el resultado en ICP (campo o __none__).')
        if result:
            # Si se devolvio un nombre, debe ser un campo real m2o(sale.order)
            f = self.env['mrp.production']._fields.get(result)
            self.assertIsNotNone(f, f'El campo devuelto {result} debe existir en el modelo.')
            self.assertEqual(f.type, 'many2one')
            self.assertEqual(f.comodel_name, 'sale.order')
            self.assertNotEqual(result, 'sale_id',
                                'El helper NO debe devolver sale_id estandar.')
        else:
            # No campo Studio detectado -> debe haberse cacheado __none__
            self.assertEqual(cached, '__none__',
                             'Sin campo Studio, el ICP debe quedar con __none__.')

    def test_09_get_sale_order_priority_standard(self):
        """_apunts_get_sale_order devuelve sale_id estandar si esta poblado."""
        partner = self.env['res.partner'].create({'name': 'Test Cliente'})
        so = self.env['sale.order'].create({'partner_id': partner.id})
        # Usar sudo para sortear ACL si las hay
        self.mo.sudo().sale_id = so.id
        result = self.mo._apunts_get_sale_order()
        self.assertEqual(result, so,
                         'Con sale_id estandar poblado el helper debe devolver esa SO.')

    def test_10_get_sale_order_empty_when_no_link(self):
        """Sin sale_id ni campo Studio detectado, el helper devuelve recordset vacio."""
        result = self.mo._apunts_get_sale_order()
        self.assertFalse(result,
                         'Sin SO vinculada de ninguna forma -> recordset sale.order vacio.')
        self.assertEqual(result._name, 'sale.order',
                         'Aun vacio, debe ser un recordset sale.order para uso uniforme.')

    def test_11_studio_override_disabled(self):
        """Si ICP = '__none__', el helper NO auto-detecta y devuelve ''."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('apunts_costes_of.studio_sale_field', '__none__')
        result = self.env['mrp.production']._apunts_get_studio_sale_field()
        self.assertEqual(result, '',
                         '__none__ es override manual -> auto-deteccion deshabilitada.')

    # ============================================================
    # HITO 12 - UX OFs no iniciadas (pending display + cap %)
    # ============================================================

    def test_h12_activity_state_no_activity(self):
        """OF confirmed sin productivity ni moves done -> activity_state='no_activity'."""
        self.mo.action_confirm()
        # Sin tocar moves done ni picar productivity
        self.mo._do_compute_apunts_costs()
        self.assertEqual(self.mo.apunts_activity_state, 'no_activity',
                         'OF confirmed sin actividad debe tener activity_state=no_activity.')
        self.assertIn('sin actividad', self.mo.apunts_activity_label.lower())

    def test_h12_activity_state_done(self):
        """OF en state=done -> activity_state='done', label 'OF completa'."""
        # Forzar state=done sin pasar por todo el flujo
        self.mo.write({'state': 'done'})
        self.mo._do_compute_apunts_costs()
        self.assertEqual(self.mo.apunts_activity_state, 'done')
        self.assertEqual(self.mo.apunts_activity_label, 'OF completa')

    def test_h12_pending_displays(self):
        """Si plan>0 y real=0, los booleans pending deben ser True y meta_display 'Plan: X EUR'."""
        # Confirmamos sin consumir nada -> mat_real=0 pero mat_plan>0 (50 EUR)
        self.mo.action_confirm()
        self.mo._do_compute_apunts_costs()
        self.assertTrue(self.mo.apunts_material_pending,
                        'Material plan=50EUR / real=0 -> pending True.')
        self.assertTrue(self.mo.apunts_total_pending)
        self.assertIn('Plan:', self.mo.apunts_material_meta_display,
                      'Pending -> meta empieza por "Plan:".')
        self.assertEqual(self.mo.apunts_material_dev_display, '',
                         'Pending -> dev display vacio (no se muestra %).')

    def test_h12_dev_cap_at_999(self):
        """Si dev > 999% el display debe ser '>999%' y el float capeado a 999.9."""
        # Simulamos: real=10000, plan=10 -> dev=99900%
        # Llamamos directamente a _compute con valores forzados via setattr no es trivial;
        # asi que probamos la logica via _dev_display y el setter del float.
        # Como _dev_display vive dentro del compute, en este test verificamos via attr cap.
        # Saltamos a una OF que no tiene plan y forzamos store con write.
        # Caso facil: plan>0, real grande -> capeo float
        self.mo.action_confirm()
        # Hack: setear direct moves done con qty enorme para inflar mat_real
        for m in self.mo.move_raw_ids:
            m.write({'state': 'done', 'quantity': 10000.0})  # 10000 unidades de MP a 5 EUR = 50000 EUR
        self.mo._do_compute_apunts_costs()
        # mat_real = 50000, mat_plan = 50 -> dev = 99900%
        self.assertEqual(self.mo.apunts_material_dev_pct, 999.9,
                         'Dev pct debe estar capeado a 999.9.')
        # v18.0.10 Bug 2: dev_display ahora formatea "Delta +X EUR (+Y%)" o
        # "Delta +X EUR (>999%)" cuando excede. Verificamos solo que contiene
        # el cap ">999%" y el delta EUR positivo.
        self.assertIn('>999%', self.mo.apunts_material_dev_display,
                      'Dev display debe contener ">999%" cuando excede el cap.')

    # ============================================================
    # HITO 10 - Editor horas productivity (admin)
    # ============================================================

    def test_h10_editor_admin_action_returns_act_window(self):
        """Como admin (test runner es superuser), la accion devuelve un act_window correcto."""
        action = self.mo.action_apunts_open_productivity_editor()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'mrp.workcenter.productivity')
        # Domain debe filtrar por la OF
        self.assertIn(('workorder_id.production_id', '=', self.mo.id), action['domain'])
        # Context debe llevar apunts_production_id para que el domain del field workorder_id funcione
        self.assertEqual(action['context'].get('apunts_production_id'), self.mo.id)
        self.assertTrue(action['context'].get('apunts_productivity_editor'))

    def test_h10_editor_non_admin_blocked(self):
        """Un usuario sin base.group_system NO puede abrir el editor — AccessError."""
        # Crear user con solo group_mrp_user (no admin)
        group_user = self.env.ref('mrp.group_mrp_user')
        group_internal = self.env.ref('base.group_user')
        non_admin = self.env['res.users'].create({
            'name': 'Test Operario MRP',
            'login': 'test_operario_mrp',
            'groups_id': [(6, 0, [group_user.id, group_internal.id])],
        })
        # Verificar que efectivamente NO esta en group_system
        self.assertFalse(non_admin.has_group('base.group_system'))
        with self.assertRaises(AccessError):
            self.mo.with_user(non_admin).action_apunts_open_productivity_editor()

    def test_h10_recalc_after_edit_regenerates_lines(self):
        """action_apunts_recalc_after_edit invalida cache, regenera lineas y devuelve notification."""
        self.mo.action_confirm()
        self.mo._apunts_regenerate_lines()
        n_before = len(self.mo.apunts_material_line_ids)
        action = self.mo.action_apunts_recalc_after_edit()
        # Devuelve display_notification
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(action['params']['type'], 'success')
        # Lineas regeneradas (mismo numero porque la OF no ha cambiado, pero recreadas)
        self.assertEqual(len(self.mo.apunts_material_line_ids), n_before)

    def test_12_revenue_uses_helper(self):
        """_apunts_revenue_total usa el helper (no acceso directo a sale_id)."""
        # Crear SO con linea para el producto terminado
        partner = self.env['res.partner'].create({'name': 'Test Cliente Rev'})
        so = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product_pt.id,
                'product_uom_qty': 5.0,
                'price_unit': 200.0,
            })],
        })
        self.mo.sudo().sale_id = so.id
        # Necesitamos que la OF tenga move_finished_ids con el producto -> action_confirm la crea
        if self.mo.state == 'draft':
            self.mo.action_confirm()
        revenue = self.mo._apunts_revenue_total()
        self.assertGreater(revenue, 0,
                           'Con SO vinculada y producto terminado, revenue debe ser > 0.')
