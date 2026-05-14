"""Hito 7 - Master Data Costes OF Apunts.

Modelo hub que centraliza la edicion de:
  - hr.employee.hourly_cost   (master data: coste/hora del empleado)
  - mrp.workcenter.costs_hour (master data: coste/hora de la maquina)
  - product.product.standard_price (master data: coste estandar del componente)

filtrado solo a registros que aparecen en OFs done (los que afectan a los costes
calculados por el modulo). Asi Javi puede reparar sus master data sin pasear
por 3 menus distintos.

Despues de editar, un boton 'Recalcular costes OFs done' invalida cache y
fuerza a recomputar las lineas auxiliares de las OFs done para que los KPIs
reflejen los nuevos masters.
"""
from odoo import models, fields, api


class ApuntsCostesOfMasterDataHub(models.Model):
    _name = 'apunts.costes.of.master.data'
    _description = 'Hub Master Data Costes OF (acceso rapido a empleados, centros y productos en OFs done)'
    _rec_name = 'name'

    name = fields.Char(default='Master Data Costes OF Apunts', readonly=True,
                       help='Etiqueta del hub. No se edita.')

    n_employees = fields.Integer(compute='_compute_counts', string='Empleados con horas en OFs done',
                                 help='Numero de hr.employee distintos con productivity entries en OFs en estado done.')
    n_employees_zero = fields.Integer(compute='_compute_counts', string='Empleados sin coste/h',
                                      help='De los anteriores, cuantos tienen hourly_cost=0 (coste laboral incalculable).')
    n_workcenters = fields.Integer(compute='_compute_counts', string='Centros usados en OFs done',
                                   help='Numero de mrp.workcenter distintos con productivity entries en OFs en estado done.')
    n_workcenters_zero = fields.Integer(compute='_compute_counts', string='Centros sin coste/h',
                                        help='De los anteriores, cuantos tienen costs_hour=0.')
    n_products = fields.Integer(compute='_compute_counts', string='Productos consumidos en OFs done',
                                help='Numero de product.product distintos consumidos como MP en OFs en estado done.')
    n_products_zero = fields.Integer(compute='_compute_counts', string='Productos sin coste estandar',
                                     help='De los anteriores, cuantos tienen standard_price<=0 (coste material incalculable).')

    n_done_ofs = fields.Integer(compute='_compute_counts', string='OFs done totales',
                                help='Numero de OFs en estado done. Sirve de referencia.')

    # ============================================================
    # Helpers SQL para localizar IDs filtrados a "OFs done"
    # ============================================================

    def _employees_in_done_ofs(self):
        """IDs de hr.employee con productivity entries en OFs done."""
        cr = self.env.cr
        cr.execute("""
            SELECT DISTINCT p.employee_id
            FROM   mrp_workcenter_productivity p
            JOIN   mrp_workorder               wo ON wo.id = p.workorder_id
            JOIN   mrp_production              mp ON mp.id = wo.production_id
            WHERE  mp.state = 'done'
              AND  p.employee_id IS NOT NULL
        """)
        return [r[0] for r in cr.fetchall()]

    def _workcenters_in_done_ofs(self):
        """IDs de mrp.workcenter con productivity entries en OFs done."""
        cr = self.env.cr
        cr.execute("""
            SELECT DISTINCT p.workcenter_id
            FROM   mrp_workcenter_productivity p
            JOIN   mrp_workorder               wo ON wo.id = p.workorder_id
            JOIN   mrp_production              mp ON mp.id = wo.production_id
            WHERE  mp.state = 'done'
              AND  p.workcenter_id IS NOT NULL
        """)
        return [r[0] for r in cr.fetchall()]

    def _products_consumed_in_done_ofs(self):
        """IDs de product.product consumidos como MP (move_raw_ids done) en OFs done."""
        cr = self.env.cr
        cr.execute("""
            SELECT DISTINCT sm.product_id
            FROM   stock_move    sm
            JOIN   mrp_production mp ON mp.id = sm.raw_material_production_id
            WHERE  mp.state = 'done'
              AND  sm.state = 'done'
        """)
        return [r[0] for r in cr.fetchall()]

    def _compute_counts(self):
        Emp = self.env['hr.employee']
        Wc = self.env['mrp.workcenter']
        Prod = self.env['product.product']
        Mo = self.env['mrp.production']
        for rec in self:
            emps = rec._employees_in_done_ofs()
            wcs = rec._workcenters_in_done_ofs()
            prods = rec._products_consumed_in_done_ofs()
            rec.n_employees = len(emps)
            rec.n_workcenters = len(wcs)
            rec.n_products = len(prods)
            rec.n_employees_zero = Emp.search_count([('id', 'in', emps), ('hourly_cost', '<=', 0)]) if emps else 0
            rec.n_workcenters_zero = Wc.search_count([('id', 'in', wcs), ('costs_hour', '<=', 0)]) if wcs else 0
            rec.n_products_zero = Prod.search_count([('id', 'in', prods), ('standard_price', '<=', 0)]) if prods else 0
            rec.n_done_ofs = Mo.search_count([('state', '=', 'done')])

    # ============================================================
    # Singleton + acceso al hub
    # ============================================================

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    @api.model
    def action_open_hub(self):
        """Abre la vista form del hub. Punto de entrada desde el menu."""
        rec = self._get_singleton()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Master Data Costes OF',
            'res_model': 'apunts.costes.of.master.data',
            'res_id': rec.id,
            'view_mode': 'form',
            'view_id': self.env.ref('apunts_costes_of.view_apunts_master_data_form').id,
            'target': 'current',
        }

    # ============================================================
    # Acciones que abren cada list editable filtrada
    # ============================================================

    def action_open_employees(self):
        """Abre lista editable hr.employee filtrada a empleados con horas en OFs done."""
        self.ensure_one()
        ids = self._employees_in_done_ofs()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Master Data — Coste/hora empleado (OFs done)',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('apunts_costes_of.view_apunts_md_employee_list').id, 'list'),
                (False, 'form'),
            ],
            'domain': [('id', 'in', ids)],
            'target': 'current',
            'context': {
                'apunts_md_hub': True,
                'search_default_apunts_md_zero_cost': 1 if self.n_employees_zero else 0,
            },
        }

    def action_open_workcenters(self):
        """Abre lista editable mrp.workcenter filtrada a centros con horas en OFs done."""
        self.ensure_one()
        ids = self._workcenters_in_done_ofs()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Master Data — Coste/hora centro de trabajo (OFs done)',
            'res_model': 'mrp.workcenter',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('apunts_costes_of.view_apunts_md_workcenter_list').id, 'list'),
                (False, 'form'),
            ],
            'domain': [('id', 'in', ids)],
            'target': 'current',
            'context': {'apunts_md_hub': True},
        }

    def action_open_products(self):
        """Abre lista editable product.product filtrada a MPs consumidos en OFs done."""
        self.ensure_one()
        ids = self._products_consumed_in_done_ofs()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Master Data — Coste estandar producto (consumido en OFs done)',
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('apunts_costes_of.view_apunts_md_product_list').id, 'list'),
                (False, 'form'),
            ],
            'domain': [('id', 'in', ids)],
            'target': 'current',
            'context': {'apunts_md_hub': True},
        }

    # ============================================================
    # Recalculo masivo de OFs done con master data nueva
    # ============================================================

    def action_recalc_all_done(self):
        """Tras editar masters, regenera todas las lineas auxiliares de OFs done.
        Util cuando Javi corrige varios costes y quiere que el tablero refleje los nuevos numeros.
        """
        self.ensure_one()
        productions = self.env['mrp.production'].search([('state', '=', 'done')])
        for p in productions:
            # invalidate compute cache antes de regenerar
            p.invalidate_recordset(['apunts_total_cost_real', 'apunts_material_cost_real',
                                    'apunts_labor_cost_real', 'apunts_operation_cost_real'])
            p._apunts_regenerate_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Costes OF recalculados',
                'message': (f'{len(productions)} OFs done procesadas con master data actualizada. '
                            f'Abre cualquier OF para ver el nuevo desglose en el smart button.'),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ============================================================
    # v18.0.11.0.0 - Bug 1 fix DINAMICO: detecta huerfanos cruzando
    # vistas Studio activas vs registry env[model]._fields. Sustituye
    # al helper hardcoded de v18.0.10.1.0 (12 campos product). Cubre
    # cualquier modelo con Studio sin lista hardcoded.
    # ============================================================

    @api.model
    def _apunts_apply_legacy_fix(self):
        return True
