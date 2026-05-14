from odoo import models, fields, api
from collections import defaultdict


def _fmt_eur(val):
    """Formatea un float como '1.234,56 EUR' en estilo es_ES, independiente del lang del user.

    Usado en strings de alertas, mensajes y campos Char autoexplicativos para que Javi
    siempre vea formato espanol consistente sin depender de la configuracion regional
    del usuario logueado.
    """
    try:
        v = float(val or 0.0)
    except (TypeError, ValueError):
        v = 0.0
    s = f"{v:,.2f}"
    s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{s} EUR"


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # Currency related (mrp.production no la trae nativa en Odoo 18)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
        string='Moneda',
        help='Moneda heredada de la company. Determina el formateo de todos los campos monetarios del modulo.',
    )

    # ============================================================
    # HITO 11 - SOPORTE CAMPO STUDIO (m2o sale.order via Studio)
    # ============================================================
    # JR (y muchos clientes Odoo) vinculan OF a SaleOrder a traves de un campo
    # custom anyadido por Odoo Studio (ej. `x_studio_venta`) en lugar del
    # `sale_id` estandar. El modulo detecta y soporta ambos transparentemente.
    # ============================================================

    @api.model
    def _apunts_get_studio_sale_field(self):
        """Devuelve el nombre del campo Studio que vincula mrp.production con sale.order, o ''.

        Resolucion en orden:
          1. ir.config_parameter 'apunts_costes_of.studio_sale_field' si esta seteado
             y apunta a un campo m2o(sale.order) realmente presente en el modelo.
             Valor especial '__none__' = override manual para deshabilitar la detection.
          2. Auto-deteccion: primer campo `x_*` o `x_studio_*` en el modelo que sea
             m2o hacia 'sale.order'. Se cachea en el ICP para ahorrar lookup.
          3. '' si no hay nada.

        Sirve como single-source-of-truth para el helper `_apunts_get_sale_order(self)`.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        param = ICP.get_param('apunts_costes_of.studio_sale_field') or ''
        if param == '__none__':
            return ''
        if param and param in self._fields:
            f = self._fields[param]
            if f.type == 'many2one' and f.comodel_name == 'sale.order':
                return param
        # Auto-detect (preferimos prefijo x_studio_ pero aceptamos cualquier x_)
        candidates_studio = []
        candidates_x = []
        for fname, field in self._fields.items():
            if field.type != 'many2one' or field.comodel_name != 'sale.order':
                continue
            if fname == 'sale_id':
                continue
            if fname.startswith('x_studio_'):
                candidates_studio.append(fname)
            elif fname.startswith('x_'):
                candidates_x.append(fname)
        chosen = ''
        if candidates_studio:
            chosen = sorted(candidates_studio)[0]
        elif candidates_x:
            chosen = sorted(candidates_x)[0]
        if chosen:
            ICP.set_param('apunts_costes_of.studio_sale_field', chosen)
        else:
            ICP.set_param('apunts_costes_of.studio_sale_field', '__none__')
        return chosen

    def _apunts_get_sale_order(self):
        """Devuelve la sale.order vinculada a esta OF (recordset, posiblemente vacio).

        Prioridad:
          1. `sale_id` estandar de Odoo si esta poblado.
          2. Campo Studio detectado (ej. `x_studio_venta` en JR) si esta poblado.
          3. sale.order vacio.

        Es el helper canonico para revenue, margen, traza forward y drill comercial.
        Substituye TODOS los usos directos de `production.sale_id` en el modulo.
        """
        self.ensure_one()
        SaleOrder = self.env['sale.order']
        if 'sale_id' in self._fields and self.sale_id:
            return self.sale_id
        fname = self._apunts_get_studio_sale_field()
        if fname and fname in self._fields:
            so = self[fname]
            if so:
                return so
        return SaleOrder

    # --- KPI scalars: REAL (siempre frescos, store=False)

    apunts_material_cost_real = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Material consumido',
        help='Coste real de los componentes ya consumidos. SUM(stock.move done.quantity x product.standard_price) sobre move_raw_ids. Si standard_price=0 en algun producto, sale infravalorado y aparece alerta.',
    )
    apunts_labor_cost_real = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Mano de obra empleado',
        help='Coste laboral real imputado: SUM(productivity.duration/60 x hr.employee.hourly_cost) sobre productivity entries con employee_id. Si hourly_cost=0, sale 0 y aparece alerta en master data.',
    )
    apunts_operation_cost_real = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Operacion centro/maquina',
        help='Coste de uso de maquinas: SUM(productivity.duration/60 x mrp.workcenter.costs_hour). Independiente del coste empleado.',
    )
    apunts_total_cost_real = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Coste total real',
        help='Suma de material consumido + mano de obra empleado + operacion centro. Es el coste real total imputado a la OF a dia de hoy.',
    )

    # --- KPI scalars: PLANIFICADO (teorico desde BoM y routing)

    apunts_material_cost_planned = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Material teorico',
        help='Coste material teorico segun BoM x cantidad de la OF. SUM(bom_line.product_qty x ratio x standard_price). Sirve como baseline para detectar desviaciones.',
    )
    apunts_labor_cost_planned = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Mano de obra teorica',
        help='Coste laboral teorico segun routing del BoM: SUM(time_cycle_manual/60 x workcenter.employee_costs_hour x ratio).',
    )
    apunts_operation_cost_planned = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Operacion teorica',
        help='Coste operacion teorico segun routing: SUM(time_cycle_manual/60 x workcenter.costs_hour x ratio).',
    )
    apunts_total_cost_planned = fields.Monetary(
        compute='_compute_apunts_costs',
        currency_field='currency_id',
        string='Coste total teorico',
        help='Material teorico + mano de obra teorica + operacion teorica. Es lo que la OF deberia costar segun BoM y routing.',
    )

    # --- Desviaciones y porcentajes

    apunts_material_dev_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                           string='Desv. material (%)',
                                           help='(material_real - material_teorico) / material_teorico x 100. Negativo = sobramos material; positivo = sobreconsumo.')
    apunts_labor_dev_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                        string='Desv. mano obra (%)',
                                        help='(MO_real - MO_teorica) / MO_teorica x 100.')
    apunts_operation_dev_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                            string='Desv. operacion (%)',
                                            help='(operacion_real - operacion_teorica) / operacion_teorica x 100.')
    apunts_total_dev_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                        string='Desv. total (%)',
                                        help='Desviacion del coste total. Umbrales: >10% atencion (ambar), >25% critico (rojo).')

    apunts_provision_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                        string='% aprovisionamiento',
                                        help='(consumido + reservado + de_camino) / necesario_total x 100. Indica si tienes la MP cubierta. <50% rojo, <80% ambar.')
    apunts_progress_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                       string='% completado',
                                       help='qty_producing / product_qty x 100. Si state=done, 100%. Mide avance fisico de fabricacion.')

    apunts_alert_count = fields.Integer(compute='_compute_apunts_costs', string='Alertas',
                                        help='Numero de alertas activas. Cada una se ve detallada en la pestana Alertas.')
    apunts_traffic_light = fields.Selection([
        ('green', 'OK'),
        ('amber', 'Atencion'),
        ('red', 'Critica'),
    ], compute='_compute_apunts_costs', string='Semaforo',
       help='Verde = todo OK; Ambar = al menos 1 alerta o desviacion >10%; Rojo = >=3 alertas o desviacion >25% o aprovisionamiento <50%.')

    apunts_kpi_button_label = fields.Char(compute='_compute_apunts_costs',
                                          string='Etiqueta smart button',
                                          help='Subtexto compacto que aparece bajo el smart button "Costes" — actualmente muestra el % de aprovisionamiento global.')

    # --- Hito 12: estado de actividad de la OF (drives badge y display)

    apunts_activity_state = fields.Selection([
        ('no_activity', 'Sin actividad'),
        ('in_progress', 'En curso'),
        ('done',        'Completa'),
        ('cancel',      'Cancelada'),
    ], compute='_compute_apunts_costs', string='Estado de actividad',
       help='no_activity = OF abierta sin productivity ni moves done; in_progress = hay actividad real; done = completa; cancel = cancelada. Drives el pill de actividad en la cabecera.')
    apunts_activity_label = fields.Char(
        compute='_compute_apunts_costs', string='Texto pill actividad',
        help='Texto que se muestra en el pill de actividad de la cabecera de la vista form alternativa.')

    # --- Hito 12: pendientes (real==0 y plan>0) por KPI -> drives display "Pendiente"

    apunts_material_pending = fields.Boolean(compute='_compute_apunts_costs',
                                             help='True si material teorico > 0 y real = 0 -> mostrar "Pendiente" en vez de 0,00 EUR.')
    apunts_labor_pending = fields.Boolean(compute='_compute_apunts_costs',
                                          help='True si MO teorica > 0 y real = 0.')
    apunts_operation_pending = fields.Boolean(compute='_compute_apunts_costs',
                                              help='True si operacion teorica > 0 y real = 0.')
    apunts_total_pending = fields.Boolean(compute='_compute_apunts_costs',
                                          help='True si coste total teorico > 0 y real = 0 (OF abierta sin actividad).')

    # --- Hito 12: subtexto KPI ("Plan: 16,25 €") y dev display capeado

    apunts_material_meta_display = fields.Char(compute='_compute_apunts_costs',
                                               help='Subtexto KPI material. Si pending: "Plan: X EUR"; si activo: "vs teor. X EUR".')
    apunts_labor_meta_display = fields.Char(compute='_compute_apunts_costs')
    apunts_operation_meta_display = fields.Char(compute='_compute_apunts_costs')
    apunts_total_meta_display = fields.Char(compute='_compute_apunts_costs')

    apunts_material_dev_display = fields.Char(compute='_compute_apunts_costs',
                                              help='v18.0.10: Delta display "Delta +X EUR (+Y%)" o "" si pending. Capea Y% a +/-999%.')
    apunts_labor_dev_display = fields.Char(compute='_compute_apunts_costs')
    apunts_operation_dev_display = fields.Char(compute='_compute_apunts_costs')
    apunts_total_dev_display = fields.Char(compute='_compute_apunts_costs')

    # --- v18.0.10: Bug 2 - rediseno KPI cards "Va a costar / Esta costando"
    # Patron: SIEMPRE 2 cifras visibles. Si OF done, invertir orden (real arriba, plan abajo).
    # apunts_invert_kpi global (state == 'done') drives la inversion en XML.
    # apunts_<kpi>_real_state colorea la cifra "Esta costando" segun ratio real/plan.

    apunts_invert_kpi = fields.Boolean(
        compute='_compute_apunts_costs',
        string='Invertir KPI cards (OF done)',
        help='True si OF done -> arriba muestra real ("Costo:"), abajo plan ("Plan era:"). False -> arriba plan ("Va a costar:"), abajo real ("Esta costando:").')

    apunts_material_real_state = fields.Selection([
        ('green', 'Real ~ plan'),
        ('amber', 'Real bajo plan'),
        ('red',   'Real sobrepasa plan'),
        ('gray',  'Sin plan o sin actividad'),
    ], compute='_compute_apunts_costs',
       help='Color para la cifra "Esta costando" en la KPI card material: gray si plan=0 o real=0, amber si real<90% plan, green si 90-110%, red si >110%.')
    apunts_labor_real_state = fields.Selection([
        ('green', 'Real ~ plan'), ('amber', 'Real bajo plan'),
        ('red', 'Real sobrepasa plan'), ('gray', 'Sin plan o sin actividad'),
    ], compute='_compute_apunts_costs')
    apunts_operation_real_state = fields.Selection([
        ('green', 'Real ~ plan'), ('amber', 'Real bajo plan'),
        ('red', 'Real sobrepasa plan'), ('gray', 'Sin plan o sin actividad'),
    ], compute='_compute_apunts_costs')
    apunts_total_real_state = fields.Selection([
        ('green', 'Real ~ plan'), ('amber', 'Real bajo plan'),
        ('red', 'Real sobrepasa plan'), ('gray', 'Sin plan o sin actividad'),
    ], compute='_compute_apunts_costs')

    # --- Hito 8: estado y lectura comercial del margen

    apunts_margin_state = fields.Selection([
        ('green', 'Margen sano (>=20%)'),
        ('amber', 'Margen ajustado (0-20%)'),
        ('red', 'Margen NEGATIVO (estamos perdiendo dinero)'),
        ('blue', 'Sin pedido cliente vinculado (produccion a stock)'),
    ], compute='_compute_apunts_costs', string='Estado margen comercial',
       help='Verde = margen >=20%; Ambar = entre 0% y 20%; Rojo = negativo; Azul = OF a stock sin SO. Threshold ajustado para que Javi vea claro cuando esta perdiendo dinero.')
    apunts_margin_explanation = fields.Char(
        compute='_compute_apunts_costs', string='Lectura comercial',
        help='Frase autoexplicativa del margen estilo "Vendi a X EUR/u, me cuesta Y EUR/u. Margen Z EUR (W%)". Disenada para que Javi entienda al vuelo el resultado economico de cada OF sin tener que leer 4 columnas separadas.')

    # --- Lineas (TransientModel: se rellenan al abrir vista)

    apunts_material_line_ids = fields.One2many(
        'apunts.costes.of.material.line', 'production_id', string='Lineas de material')
    apunts_labor_line_ids = fields.One2many(
        'apunts.costes.of.labor.line', 'production_id', string='Lineas de mano de obra')
    apunts_attendance_line_ids = fields.One2many(
        'apunts.costes.of.attendance.line', 'production_id',
        string='Lineas asistencia (empleado x dia)')
    apunts_finished_line_ids = fields.One2many(
        'apunts.costes.of.finished.line', 'production_id',
        string='Lineas producto terminado')
    apunts_alert_ids = fields.One2many(
        'apunts.costes.of.alert', 'production_id', string='Alertas activas')

    # KPI agregados Hito 4 (margen comercial)
    apunts_revenue_total = fields.Monetary(compute='_compute_apunts_costs',
                                           currency_field='currency_id',
                                           string='Ingreso comercial total (EUR)')
    apunts_margin_total = fields.Monetary(compute='_compute_apunts_costs',
                                          currency_field='currency_id',
                                          string='Margen comercial total (EUR)')
    apunts_margin_pct = fields.Float(compute='_compute_apunts_costs', digits=(16, 1),
                                     string='Margen %')

    # ============================================================
    # COMPUTE PRINCIPAL DE KPIS
    # ============================================================

    @api.depends(
        'move_raw_ids', 'move_raw_ids.state', 'move_raw_ids.product_uom_qty',
        'move_raw_ids.quantity',
        'workorder_ids', 'workorder_ids.duration', 'workorder_ids.duration_expected',
        'product_qty', 'qty_producing', 'bom_id', 'state',
    )
    def _compute_apunts_costs(self):
        for prod in self:
            prod._do_compute_apunts_costs()

    def _do_compute_apunts_costs(self):
        """Calcula los KPIs scalars de coste y semaforo. Sin tocar tablas auxiliares."""
        self.ensure_one()
        # Material
        mat_real = self._apunts_material_real()
        mat_plan = self._apunts_material_planned()
        # Mano de obra (empleado) y operacion (centro)
        labor_real, oper_real = self._apunts_labor_and_operation_real()
        labor_plan, oper_plan = self._apunts_labor_and_operation_planned()

        total_real = mat_real + labor_real + oper_real
        total_plan = mat_plan + labor_plan + oper_plan

        # Hito 12: capeamos el dev a +/-999.9 para no mostrar -10000%
        # cuando real es residual o plan es marginal. El display Char ya formatea
        # ">999%" / "<-999%" pero capear el float evita que widget="percentage"
        # rinda numeros estridentes en otros sitios.
        def _dev(real, plan):
            if not plan:
                return 0.0
            pct = round((real - plan) / plan * 100, 1)
            if pct > 999.9:
                return 999.9
            if pct < -999.9:
                return -999.9
            return pct

        def _dev_display(real, plan):
            """v18.0.10 Bug 2: 'Delta +X EUR (+Y%)' completo. '' si pending o sin plan.

            Capea pct a +/-999% para no mostrar -10000% feos. El delta EUR es real-plan.
            Signo: positivo si real>plan (sobrecoste, malo para coste), negativo si real<plan.
            """
            if not plan:
                return ''
            if real == 0:
                return ''
            raw_pct = (real - plan) / plan * 100
            delta_eur = real - plan
            sign = '+' if delta_eur >= 0 else ''
            if raw_pct > 999.9:
                pct_str = '>999%'
            elif raw_pct < -999.9:
                pct_str = '<-999%'
            else:
                pct_str = f"{raw_pct:+.1f}%"
            return f"Δ {sign}{_fmt_eur(delta_eur)} ({pct_str})"

        def _real_state(real, plan):
            """Color para la cifra 'Esta costando': gray si plan=0 o real=0, amber si <90%, green 90-110%, red >110%."""
            if not plan or real == 0:
                return 'gray'
            ratio = real / plan
            if ratio < 0.9:
                return 'amber'
            if ratio <= 1.1:
                return 'green'
            return 'red'

        def _meta_display(real, plan):
            """Subtexto del KPI card. Pending -> 'Plan: X EUR'; activo -> 'vs teor. X EUR'."""
            if not plan:
                return ''
            if real == 0:
                return f"Plan: {_fmt_eur(plan)}"
            return f"vs teor. {_fmt_eur(plan)}"

        # Aprovisionamiento y progreso
        prov_pct = self._apunts_provision_pct()
        progress_pct = self._apunts_progress_pct()

        # Semaforo y alertas
        alert_count = self._apunts_count_active_alerts(prov_pct, _dev(total_real, total_plan))
        traffic = self._apunts_traffic_light(prov_pct, _dev(total_real, total_plan), alert_count)

        self.apunts_material_cost_real = mat_real
        self.apunts_labor_cost_real = labor_real
        self.apunts_operation_cost_real = oper_real
        self.apunts_total_cost_real = total_real

        self.apunts_material_cost_planned = mat_plan
        self.apunts_labor_cost_planned = labor_plan
        self.apunts_operation_cost_planned = oper_plan
        self.apunts_total_cost_planned = total_plan

        self.apunts_material_dev_pct = _dev(mat_real, mat_plan)
        self.apunts_labor_dev_pct = _dev(labor_real, labor_plan)
        self.apunts_operation_dev_pct = _dev(oper_real, oper_plan)
        self.apunts_total_dev_pct = _dev(total_real, total_plan)

        self.apunts_provision_pct = prov_pct
        self.apunts_progress_pct = progress_pct
        self.apunts_alert_count = alert_count
        self.apunts_traffic_light = traffic
        self.apunts_kpi_button_label = f'{prov_pct:.0f}% aprov.'

        # ============================================================
        # HITO 12 - Estado actividad + display "Pendiente" + cap %
        # ============================================================
        # Estado actividad: drives badge en cabecera vista form alternativa.
        has_productivity = bool(self.workorder_ids and any(
            wo.duration > 0 for wo in self.workorder_ids
        ))
        has_moves_done = bool(self.move_raw_ids.filtered(lambda m: m.state == 'done'))
        if self.state == 'cancel':
            self.apunts_activity_state = 'cancel'
            self.apunts_activity_label = 'OF cancelada'
        elif self.state == 'done':
            self.apunts_activity_state = 'done'
            self.apunts_activity_label = 'OF completa'
        elif self.state in ('progress', 'to_close', 'confirmed') and not has_productivity and not has_moves_done:
            self.apunts_activity_state = 'no_activity'
            self.apunts_activity_label = 'OF abierta — sin actividad registrada'
        else:
            self.apunts_activity_state = 'in_progress'
            self.apunts_activity_label = 'OF en curso'

        # Pending booleans por KPI
        self.apunts_material_pending = bool(mat_plan > 0 and mat_real == 0)
        self.apunts_labor_pending = bool(labor_plan > 0 and labor_real == 0)
        self.apunts_operation_pending = bool(oper_plan > 0 and oper_real == 0)
        self.apunts_total_pending = bool(total_plan > 0 and total_real == 0)

        # Meta display + dev display por KPI
        self.apunts_material_meta_display = _meta_display(mat_real, mat_plan)
        self.apunts_labor_meta_display = _meta_display(labor_real, labor_plan)
        self.apunts_operation_meta_display = _meta_display(oper_real, oper_plan)
        self.apunts_total_meta_display = _meta_display(total_real, total_plan)

        self.apunts_material_dev_display = _dev_display(mat_real, mat_plan)
        self.apunts_labor_dev_display = _dev_display(labor_real, labor_plan)
        self.apunts_operation_dev_display = _dev_display(oper_real, oper_plan)
        self.apunts_total_dev_display = _dev_display(total_real, total_plan)

        # v18.0.10 Bug 2: invertir KPI cards si OF done; colorear "Esta costando".
        self.apunts_invert_kpi = bool(self.state == 'done')
        self.apunts_material_real_state = _real_state(mat_real, mat_plan)
        self.apunts_labor_real_state = _real_state(labor_real, labor_plan)
        self.apunts_operation_real_state = _real_state(oper_real, oper_plan)
        self.apunts_total_real_state = _real_state(total_real, total_plan)

        # Hito 4: margen comercial (revenue desde sale.order.line vinculadas)
        # Hito 11: revenue ya respeta tanto sale_id estandar como campo Studio.
        revenue = self._apunts_revenue_total()
        margin_total = round(revenue - total_real, 2) if revenue else 0.0
        margin_pct = round((revenue - total_real) / revenue * 100, 1) if revenue else 0.0
        self.apunts_revenue_total = revenue
        self.apunts_margin_total = margin_total
        self.apunts_margin_pct = margin_pct
        # Hito 8: estado margen + frase autoexplicativa (threshold 20% segun nota Javi)
        if not revenue:
            self.apunts_margin_state = 'blue'
            self.apunts_margin_explanation = (
                'Esta OF produce a stock — no hay pedido cliente vinculado, '
                'por lo que no se calcula margen comercial. Si la pieza se vende mas adelante, '
                'el margen aparecera aqui automaticamente al cruzar el sale.order.'
            )
        elif margin_total < 0:
            self.apunts_margin_state = 'red'
            self.apunts_margin_explanation = (
                f'Vendimos por {_fmt_eur(revenue)}, nos costo {_fmt_eur(total_real)}. '
                f'PERDEMOS {_fmt_eur(abs(margin_total))} ({margin_pct:+.1f}%). '
                f'Hay que subir precio, dejar de fabricar o renegociar materia prima.'
            )
        elif margin_pct < 20:
            self.apunts_margin_state = 'amber'
            self.apunts_margin_explanation = (
                f'Vendimos por {_fmt_eur(revenue)}, nos costo {_fmt_eur(total_real)}. '
                f'Margen {_fmt_eur(margin_total)} ({margin_pct:+.1f}%) — ajustado. '
                f'Por debajo del 20% conviene revisar precio o costes.'
            )
        else:
            self.apunts_margin_state = 'green'
            self.apunts_margin_explanation = (
                f'Vendimos por {_fmt_eur(revenue)}, nos costo {_fmt_eur(total_real)}. '
                f'Margen {_fmt_eur(margin_total)} ({margin_pct:+.1f}%).'
            )

    # ============================================================
    # CALCULOS - MATERIAL
    # ============================================================

    def _apunts_get_related_pos(self):
        """POs vinculadas a esta OF (por procurement_group, origin O campo
        custom `fabricacion` de purchase.order.line — vínculo manual del cliente)."""
        self.ensure_one()
        PO = self.env['purchase.order']
        POL = self.env['purchase.order.line']
        pos = PO
        if self.procurement_group_id:
            pos |= PO.search([
                ('group_id', '=', self.procurement_group_id.id),
                ('state', 'in', ('purchase', 'done')),
            ])
        if self.name:
            pos |= PO.search([
                ('origin', 'ilike', self.name),
                ('state', 'in', ('purchase', 'done')),
            ])
        # NUEVO: vínculo manual del cliente vía campo `fabricacion` en pol
        if 'fabricacion' in POL._fields:
            pols = POL.search([
                ('fabricacion', '=', self.id),
                ('order_id.state', 'in', ('purchase', 'done')),
            ])
            pos |= pols.order_id
        return pos

    def _apunts_material_real(self):
        """Material 'real' = lo realmente comprometido / gastado en MP.

        Cascada de fuentes por componente:
        1. Move DONE → qty consumida × precio (valor más fiel).
        2. Move NO done con `purchase_line_id` directo → qty_received × price_unit.
        3. Move NO done sin link directo, pero hay PO vinculada a la OF
           (vía procurement_group u origin) con ese mismo producto → tomar
           qty_received × price_unit de esa pol.
        4. Si nada de lo anterior → 0 (no hay coste comprometido todavía).

        El precio fallback en (1) usa cascada estándar → cae a
        `_apunts_avg_purchase_price` si standard_price=0.
        """
        self.ensure_one()
        related_pos = self._apunts_get_related_pos()
        total = 0.0
        for m in self.move_raw_ids:
            if m.state == 'cancel':
                continue
            price_fallback = m.product_id.standard_price or 0.0
            if not price_fallback:
                price_fallback = self._apunts_avg_purchase_price(m.product_id)

            # PRIORIDAD ABSOLUTA: pol con `fabricacion=self` (vínculo manual exacto JR).
            # Usar price_subtotal directo (cubre UoM secundaria correctamente).
            POL = self.env['purchase.order.line']
            if 'fabricacion' in POL._fields:
                matched_fab = POL.search([
                    ('fabricacion', '=', self.id),
                    ('product_id', '=', m.product_id.id),
                    ('order_id.state', 'in', ('purchase', 'done')),
                ])
                if matched_fab:
                    total_qty = sum(matched_fab.mapped('product_qty'))
                    total_amt = sum(matched_fab.mapped('price_subtotal'))
                    if total_qty > 0 and total_amt > 0:
                        total += total_amt
                        continue

            # Si el move tiene quantity > 0 (consumo físico ya hecho aunque
            # state aún sea 'assigned'/'progress'), contar como real consumido.
            if (m.quantity or 0) > 0:
                total += m.quantity * price_fallback
                continue

            if m.purchase_line_id:
                pol = m.purchase_line_id
                qty_recv = pol.qty_received or 0.0
                pol_price = pol.price_unit or price_fallback
                total += qty_recv * pol_price
                continue

            # Buscar pol del mismo producto en POs vinculadas a la OF.
            # PRIORIZAR las que tienen `fabricacion=self` (vínculo manual exacto).
            POL = self.env['purchase.order.line']
            matched_fab = POL.browse()
            if 'fabricacion' in POL._fields:
                matched_fab = POL.search([
                    ('fabricacion', '=', self.id),
                    ('product_id', '=', m.product_id.id),
                    ('order_id.state', 'in', ('purchase', 'done')),
                ])
            if matched_fab:
                # Usar price_subtotal/product_qty para soportar UoM secundaria
                # (donde price_unit puede estar en sec ej. €/kg pero product_qty
                # en primaria ej. m → multiplicar qty × price_unit daría error).
                total_qty = sum(matched_fab.mapped('product_qty'))
                total_amt = sum(matched_fab.mapped('price_subtotal'))
                if total_qty > 0 and total_amt > 0:
                    total += total_amt
                    continue

            matched = related_pos.order_line.filtered(
                lambda l: l.product_id.id == m.product_id.id and (l.qty_received or 0) > 0
            )
            if matched:
                for pol in matched:
                    qty_recv = pol.qty_received or 0.0
                    pol_price = pol.price_unit or price_fallback
                    total += qty_recv * pol_price
        return round(total, 2)

    def _apunts_material_planned(self):
        """Material teorico desde BoM x qty."""
        self.ensure_one()
        if not self.bom_id:
            return 0.0
        bom = self.bom_id
        bom_qty = bom.product_qty or 1.0
        target_qty = self.product_qty or 0.0
        ratio = target_qty / bom_qty if bom_qty else 0.0
        total = 0.0
        for line in bom.bom_line_ids:
            std = line.product_id.standard_price or 0.0
            if not std:
                std = self._apunts_avg_purchase_price(line.product_id)
            total += (line.product_qty or 0.0) * ratio * std
        return round(total, 2)

    # ============================================================
    # CALCULOS - MANO DE OBRA + OPERACION (centros)
    # ============================================================

    def _apunts_labor_and_operation_real(self):
        """Devuelve (labor_real_empleado, operacion_real_centro) en EUR."""
        self.ensure_one()
        cr = self.env.cr
        cr.execute("""
            SELECT
                COALESCE(SUM(p.duration / 60.0 * COALESCE(he.hourly_cost, 0)), 0)        AS coste_emp,
                COALESCE(SUM(p.duration / 60.0 * COALESCE(wc.costs_hour, 0)), 0)         AS coste_wc
            FROM   mrp_workcenter_productivity p
            JOIN   mrp_workorder               wo ON wo.id = p.workorder_id
            JOIN   mrp_workcenter              wc ON wc.id = p.workcenter_id
            LEFT   JOIN hr_employee            he ON he.id = p.employee_id
            WHERE  wo.production_id = %s
              AND  p.date_end IS NOT NULL
        """, [self.id])
        row = cr.fetchone() or (0.0, 0.0)
        return round(row[0] or 0.0, 2), round(row[1] or 0.0, 2)

    def _apunts_labor_and_operation_planned(self):
        """Plan teorico: routing de la BoM x cantidad de la OF.

        Operacion teorica: SUM(time_cycle_manual/60 x wc.costs_hour x qty/bom_qty).
        Mano de obra teorica empleado: 0 si no hay routing por empleado (caso JR).
        """
        self.ensure_one()
        if not self.bom_id:
            return 0.0, 0.0
        bom = self.bom_id
        bom_qty = bom.product_qty or 1.0
        target_qty = self.product_qty or 0.0
        ratio = target_qty / bom_qty if bom_qty else 0.0
        operation = 0.0
        labor = 0.0
        for op in bom.operation_ids:
            wc = op.workcenter_id
            time_cycle_total = (op.time_cycle_manual or 0.0)
            operation += (time_cycle_total / 60.0) * (wc.costs_hour or 0.0) * ratio
            labor += (time_cycle_total / 60.0) * (wc.employee_costs_hour or 0.0) * ratio
        return round(labor, 2), round(operation, 2)

    # ============================================================
    # CALCULOS - APROVISIONAMIENTO
    # ============================================================

    def _apunts_provision_pct(self):
        """% aprovisionamiento = (consumido + reservado + en_camino) / necesario_total x 100."""
        self.ensure_one()
        if not self.move_raw_ids:
            return 0.0
        total_needed = 0.0
        total_covered = 0.0
        for m in self.move_raw_ids:
            needed = m.product_uom_qty or 0.0
            consumed = m.quantity if m.state == 'done' else 0.0
            reserved = (m.quantity or 0.0) if m.state in ('assigned', 'partially_available') else 0.0
            in_transit = self._apunts_in_transit_qty(m)
            covered = min(needed, consumed + reserved + in_transit)
            total_needed += needed
            total_covered += covered
        return round(total_covered / total_needed * 100, 1) if total_needed else 0.0

    def _apunts_in_transit_qty(self, move):
        """Cantidad de POs vinculadas a esta OF para el producto del move, pendiente de recibir."""
        self.ensure_one()
        if not self.procurement_group_id:
            return 0.0
        cr = self.env.cr
        cr.execute("""
            SELECT COALESCE(SUM(pol.product_qty - pol.qty_received), 0)
            FROM   purchase_order_line pol
            JOIN   purchase_order      po ON po.id = pol.order_id
            WHERE  po.group_id = %s
              AND  pol.product_id = %s
              AND  po.state IN ('purchase', 'done')
              AND  pol.product_qty > pol.qty_received
        """, [self.procurement_group_id.id, move.product_id.id])
        row = cr.fetchone()
        return float(row[0]) if row else 0.0

    def _apunts_progress_pct(self):
        """% completado = qty_producing / product_qty x 100. Si done, 100%."""
        self.ensure_one()
        if self.state == 'done':
            return 100.0
        if self.product_qty:
            return round((self.qty_producing or 0.0) / self.product_qty * 100, 1)
        return 0.0

    # ============================================================
    # ALERTAS Y SEMAFORO
    # ============================================================

    def _apunts_count_active_alerts(self, prov_pct, total_dev_pct):
        """Numero de alertas que se generarian. NO crea registros en tabla apunts.costes.of.alert."""
        self.ensure_one()
        n = 0
        # Alerta MP faltante sin PO
        for m in self.move_raw_ids:
            needed = m.product_uom_qty or 0.0
            consumed = m.quantity if m.state == 'done' else 0.0
            reserved = (m.quantity or 0.0) if m.state in ('assigned', 'partially_available') else 0.0
            in_transit = self._apunts_in_transit_qty(m)
            missing = needed - consumed - reserved - in_transit
            if missing > 0.001 and self.state not in ('done', 'cancel'):
                n += 1
        # Alerta OT desbordada
        for wo in self.workorder_ids:
            if wo.duration_expected and wo.duration > wo.duration_expected * 1.15:
                n += 1
        # Alerta desviacion total
        if abs(total_dev_pct) > 25:
            n += 1
        # Alerta aprovisionamiento bajo
        if prov_pct < 50 and self.state not in ('done', 'cancel'):
            n += 1
        return n

    def _apunts_traffic_light(self, prov_pct, total_dev_pct, alert_count):
        """Verde / Ambar / Rojo segun reglas SPEC."""
        if self.state == 'cancel':
            return 'amber'
        if alert_count >= 3 or abs(total_dev_pct) > 25 or (prov_pct < 50 and self.state not in ('done', 'cancel')):
            return 'red'
        if alert_count >= 1 or abs(total_dev_pct) > 10 or (prov_pct < 80 and self.state not in ('done', 'cancel')):
            return 'amber'
        return 'green'

    # ============================================================
    # REGENERACION DE LINEAS (al abrir vista costes / refresh)
    # ============================================================

    def _apunts_regenerate_lines(self):
        """Borra y recrea todas las lineas auxiliares de la vista Costes OF.

        Hito 3 anyade attendance lines. Hito 4 anyade finished lines.
        """
        self.ensure_one()
        # Limpieza
        self.env['apunts.costes.of.material.line'].search([('production_id', '=', self.id)]).unlink()
        self.env['apunts.costes.of.labor.line'].search([('production_id', '=', self.id)]).unlink()
        self.env['apunts.costes.of.attendance.line'].search([('production_id', '=', self.id)]).unlink()
        self.env['apunts.costes.of.finished.line'].search([('production_id', '=', self.id)]).unlink()
        self.env['apunts.costes.of.alert'].search([('production_id', '=', self.id)]).unlink()

        self._apunts_create_material_lines()
        self._apunts_create_labor_lines()
        self._apunts_create_attendance_lines()
        self._apunts_create_finished_lines()
        self._apunts_create_alert_lines()

    def _apunts_create_material_lines(self):
        self.ensure_one()
        Material = self.env['apunts.costes.of.material.line']
        rows = []
        for m in self.move_raw_ids:
            needed = m.product_uom_qty or 0.0
            consumed = m.quantity if m.state == 'done' else 0.0
            reserved = (m.quantity or 0.0) if m.state in ('assigned', 'partially_available') else 0.0
            in_transit = self._apunts_in_transit_qty(m)
            missing = max(needed - consumed - reserved - in_transit, 0.0)
            std_price = m.product_id.standard_price or 0.0
            avg_purchase = self._apunts_avg_purchase_price(m.product_id)
            effective_price = std_price if std_price else avg_purchase
            cost_consumed = round(consumed * effective_price, 2)
            cost_pending = round((reserved + in_transit + missing) * effective_price, 2)
            if missing > 0.001 and self.state not in ('done', 'cancel'):
                state = 'red'
            elif consumed >= needed - 0.001 and needed > 0:
                state = 'green'
            else:
                state = 'amber'
            # PO origen (si solo una)
            po = self._apunts_po_for_product(m.product_id)
            # Hito 4: trazabilidad backward
            seller = m.product_id.seller_ids[:1]
            seller_partner = seller.partner_id if seller else False
            lot_id, lot_summary = self._apunts_lots_for_move(m)
            rows.append({
                'production_id': self.id,
                'move_id': m.id,
                'product_id': m.product_id.id,
                'product_name': m.product_id.display_name[:80],
                'uom_id': m.product_uom.id if m.product_uom else False,
                'qty_needed': needed,
                'qty_consumed': consumed,
                'qty_reserved': reserved,
                'qty_in_transit': in_transit,
                'qty_missing': missing,
                'standard_price': std_price,
                'cost_total': cost_consumed,
                'cost_pending': cost_pending,
                'cost_total_needed': round(needed * effective_price, 2),
                'state': state,
                'purchase_order_id': po.id if po else False,
                'seller_partner_id': seller_partner.id if seller_partner else False,
                'seller_partner_name': (seller_partner.name or '')[:60] if seller_partner else '',
                'avg_purchase_price': avg_purchase,
                'lot_id': lot_id,
                'lot_ids_summary': lot_summary[:120],
            })
        if rows:
            Material.create(rows)

    def _apunts_avg_purchase_price(self, product):
        """Devuelve un precio de coste para `product` con cascada de fallbacks.

        Orden de prioridad:
        1. Promedio ponderado de POs recibidas (purchase/done con qty_received > 0).
        2. Última PO confirmada (purchase/done) aunque aún no haya recepción.
        3. Promedio ponderado a nivel TEMPLATE (cubre variantes diferentes).
        4. Última PO a nivel TEMPLATE.
        5. Precio del proveedor configurado en `product.seller_ids` más reciente.
        6. `standard_price` del template si la variante lo tiene a 0.

        Garantiza que si en la ficha del producto hay CUALQUIER traza de compra,
        el coste material no salga 0.
        """
        self.ensure_one()
        if not product:
            return 0.0
        cr = self.env.cr
        tmpl_id = product.product_tmpl_id.id if product.product_tmpl_id else 0

        # 1. Promedio ponderado del producto exacto (variante) con qty_received > 0
        cr.execute("""
            SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
            FROM   purchase_order_line pol
            JOIN   purchase_order      po ON po.id = pol.order_id
            WHERE  pol.product_id = %s
              AND  po.state IN ('purchase', 'done')
              AND  pol.qty_received > 0
        """, [product.id])
        row = cr.fetchone()
        avg = float(row[0]) if row and row[0] else 0.0
        if avg > 0:
            return round(avg, 4)

        # 2. Última PO confirmada del producto exacto (variante) aunque sin recepción
        cr.execute("""
            SELECT pol.price_unit
            FROM   purchase_order_line pol
            JOIN   purchase_order      po ON po.id = pol.order_id
            WHERE  pol.product_id = %s
              AND  po.state IN ('purchase', 'done')
              AND  pol.price_unit > 0
            ORDER BY po.date_order DESC NULLS LAST, po.id DESC
            LIMIT 1
        """, [product.id])
        row = cr.fetchone()
        last = float(row[0]) if row and row[0] else 0.0
        if last > 0:
            return round(last, 4)

        # 3. Promedio ponderado a nivel TEMPLATE (cubre variantes hermanas)
        if tmpl_id:
            cr.execute("""
                SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
                FROM   purchase_order_line pol
                JOIN   purchase_order      po ON po.id = pol.order_id
                JOIN   product_product     pp ON pp.id = pol.product_id
                WHERE  pp.product_tmpl_id = %s
                  AND  po.state IN ('purchase', 'done')
                  AND  pol.qty_received > 0
            """, [tmpl_id])
            row = cr.fetchone()
            avg_t = float(row[0]) if row and row[0] else 0.0
            if avg_t > 0:
                return round(avg_t, 4)

            # 4. Última PO a nivel TEMPLATE
            cr.execute("""
                SELECT pol.price_unit
                FROM   purchase_order_line pol
                JOIN   purchase_order      po ON po.id = pol.order_id
                JOIN   product_product     pp ON pp.id = pol.product_id
                WHERE  pp.product_tmpl_id = %s
                  AND  po.state IN ('purchase', 'done')
                  AND  pol.price_unit > 0
                ORDER BY po.date_order DESC NULLS LAST, po.id DESC
                LIMIT 1
            """, [tmpl_id])
            row = cr.fetchone()
            last_t = float(row[0]) if row and row[0] else 0.0
            if last_t > 0:
                return round(last_t, 4)

        # 5. Precio del proveedor configurado en el producto
        sellers = product.seller_ids.sorted(key=lambda s: (s.sequence or 99, -(s.id or 0)))
        for seller in sellers:
            if seller.price and seller.price > 0:
                return round(seller.price, 4)

        # 6. Standard price del template (último recurso)
        if product.product_tmpl_id and product.product_tmpl_id.standard_price:
            return round(product.product_tmpl_id.standard_price, 4)

        return 0.0

    def _apunts_lots_for_move(self, move):
        """Lotes consumidos en el move via move_line_ids. Devuelve (lot_id_unico_o_False, summary_str)."""
        if not move:
            return False, ''
        lots = move.move_line_ids.lot_id
        if not lots:
            return False, ''
        names = [l.name for l in lots if l.name]
        if not names:
            return False, ''
        summary = ', '.join(names[:5]) + (' ...' if len(names) > 5 else '')
        return (lots[0].id if len(lots) == 1 else False), summary

    def _apunts_po_for_product(self, product):
        """Devuelve la PO unica vinculada a esta OF que aprovisiona ese producto, o False."""
        self.ensure_one()
        if not self.procurement_group_id or not product:
            return False
        pos = self.env['purchase.order'].search([
            ('group_id', '=', self.procurement_group_id.id),
            ('order_line.product_id', '=', product.id),
            ('state', 'in', ('purchase', 'done')),
        ], limit=2)
        return pos[:1] if len(pos) == 1 else False

    def _apunts_create_labor_lines(self):
        self.ensure_one()
        Labor = self.env['apunts.costes.of.labor.line']
        rows = []
        for wo in self.workorder_ids:
            cost_emp, cost_wc = self._apunts_wo_cost(wo)
            employees = self._apunts_wo_employees(wo)
            hours_real = round((wo.duration or 0.0) / 60.0, 2)
            hours_plan = round((wo.duration_expected or 0.0) / 60.0, 2)
            progress = round(hours_real / hours_plan * 100, 1) if hours_plan else 0.0
            if wo.state == 'done':
                state = 'green' if hours_plan and hours_real <= hours_plan * 1.15 else 'amber'
            elif hours_plan and hours_real > hours_plan * 1.15:
                state = 'red'
            elif wo.state in ('progress', 'ready'):
                state = 'amber' if hours_real > 0 else 'pending'
            else:
                state = 'pending'
            rows.append({
                'production_id': self.id,
                'workorder_id': wo.id,
                'workorder_sequence': wo.id,
                'workorder_name': wo.name,
                'workcenter_id': wo.workcenter_id.id if wo.workcenter_id else False,
                'workcenter_name': wo.workcenter_id.name if wo.workcenter_id else '',
                'operation_id': wo.operation_id.id if wo.operation_id else False,
                'hours_planned': hours_plan,
                'hours_real': hours_real,
                'progress_pct': progress,
                'cost_workcenter': cost_wc,
                'cost_employee': cost_emp,
                'cost_total': round(cost_wc + cost_emp, 2),
                'employees_count': len(employees),
                'employees_summary': ', '.join(employees[:4]) + (' ...' if len(employees) > 4 else ''),
                'state': state,
                'workorder_state': wo.state,
            })
        if rows:
            Labor.create(rows)

    def _apunts_wo_cost(self, wo):
        """Devuelve (coste_empleado, coste_workcenter) para una workorder."""
        cr = self.env.cr
        cr.execute("""
            SELECT
                COALESCE(SUM(p.duration / 60.0 * COALESCE(he.hourly_cost, 0)), 0)        AS coste_emp,
                COALESCE(SUM(p.duration / 60.0 * COALESCE(wc.costs_hour, 0)), 0)         AS coste_wc
            FROM   mrp_workcenter_productivity p
            JOIN   mrp_workcenter              wc ON wc.id = p.workcenter_id
            LEFT   JOIN hr_employee            he ON he.id = p.employee_id
            WHERE  p.workorder_id = %s
              AND  p.date_end IS NOT NULL
        """, [wo.id])
        row = cr.fetchone() or (0.0, 0.0)
        return round(row[0] or 0.0, 2), round(row[1] or 0.0, 2)

    def _apunts_wo_employees(self, wo):
        """Lista de nombres de empleados imputados a la WO (uniques)."""
        cr = self.env.cr
        cr.execute("""
            SELECT DISTINCT he.name
            FROM   mrp_workcenter_productivity p
            JOIN   hr_employee he ON he.id = p.employee_id
            WHERE  p.workorder_id = %s
              AND  p.date_end IS NOT NULL
        """, [wo.id])
        return [r[0] for r in cr.fetchall() if r[0]]

    # ============================================================
    # CALCULOS - ASISTENCIAS (Hito 3)
    # ============================================================

    def _apunts_create_attendance_lines(self):
        """Crea apunts.costes.of.attendance.line: una fila por (empleado x dia x OT) imputado a la OF.

        Permite ver con granularidad fina quien picho cada dia, en que OT, cuantas horas, a que coste.
        Si hr_employee.hourly_cost = 0 (caso JR actual), state = 'amber' como aviso visual.
        Si productivity sin employee_id (imputacion solo a centro), state = 'blue'.
        """
        self.ensure_one()
        Att = self.env['apunts.costes.of.attendance.line']
        cr = self.env.cr
        cr.execute("""
            SELECT
                p.employee_id,
                COALESCE(he.name, '') AS employee_name,
                COALESCE(he.hourly_cost, 0)::float AS hourly_cost,
                wo.id AS workorder_id,
                wo.name AS workorder_name,
                wc.id AS workcenter_id,
                wc.name AS workcenter_name,
                DATE(p.date_start) AS day_date,
                COALESCE(SUM(p.duration), 0)::float / 60.0 AS hours
            FROM   mrp_workcenter_productivity p
            JOIN   mrp_workorder               wo ON wo.id = p.workorder_id
            JOIN   mrp_workcenter              wc ON wc.id = p.workcenter_id
            LEFT   JOIN hr_employee            he ON he.id = p.employee_id
            WHERE  wo.production_id = %s
              AND  p.date_end IS NOT NULL
            GROUP BY p.employee_id, he.name, he.hourly_cost,
                     wo.id, wo.name, wc.id, wc.name, DATE(p.date_start)
            ORDER BY DATE(p.date_start), he.name, wo.name
        """, [self.id])
        rows_in = cr.fetchall()
        rows = []
        for r in rows_in:
            (emp_id, emp_name, hourly, wo_id, wo_name, wc_id, wc_name, day_date, hours) = r
            hours = round(hours or 0.0, 2)
            hourly = round(hourly or 0.0, 2)
            cost_total = round(hours * hourly, 2)
            if not emp_id:
                state = 'blue'
            elif hourly <= 0:
                state = 'amber'
            else:
                state = 'green'
            rows.append({
                'production_id': self.id,
                'workorder_id': wo_id,
                'workorder_name': wo_name,
                'workcenter_id': wc_id,
                'workcenter_name': wc_name,
                'employee_id': emp_id or False,
                'employee_name': emp_name or '(Sin empleado)',
                'day_date': day_date,
                'day_label': day_date.strftime('%d/%m/%Y') if day_date else '',
                'hours': hours,
                'hourly_cost': hourly,
                'cost_total': cost_total,
                'state': state,
            })
        if rows:
            Att.create(rows)

    # ============================================================
    # CALCULOS - PRODUCTO TERMINADO + MARGEN (Hito 4)
    # ============================================================

    def _apunts_create_finished_lines(self):
        """Crea apunts.costes.of.finished.line: una fila por move_finished_ids done.

        Trazabilidad forward: lote producido + albaran de salida + SO + cliente + margen comercial.
        Si la OF no tiene SO vinculada (produccion a stock), state='blue' y margen vacio.
        """
        self.ensure_one()
        Fin = self.env['apunts.costes.of.finished.line']
        cost_real = self.apunts_total_cost_real or 0.0
        rows = []
        # Identificar SO vinculada a la OF (si existe).
        # Hito 11: usar helper que respeta sale_id estandar Y campo Studio (x_studio_venta en JR).
        so = self._apunts_get_sale_order()
        partner = so.partner_id if so else False
        # Iterar sobre moves del producto terminado de la OF.
        for m in self.move_finished_ids:
            if m.state == 'cancel':
                continue
            qty = m.quantity if m.state == 'done' else (m.product_uom_qty or 0.0)
            # Lote: lookup en move_line_ids
            lots = m.move_line_ids.lot_id
            lot = lots[:1] if lots else False
            lot_name = ', '.join([l.name for l in lots if l.name][:3])
            # Albaran salida (picking) — buscar el siguiente move outgoing del mismo producto/lote en la cadena.
            picking = self._apunts_outgoing_picking_for_move(m)
            picking_state = picking.state if picking else ''
            delivery_date = picking.scheduled_date.date() if (picking and picking.scheduled_date) else False
            # SO line — preferir sale_line_id explicito en move; fallback a SO de la OF
            sol = m.sale_line_id if hasattr(m, 'sale_line_id') and m.sale_line_id else False
            if not sol and so:
                sol = so.order_line.filtered(lambda l: l.product_id.id == m.product_id.id)[:1]
            sale_price_unit = sol.price_unit if sol else 0.0
            sale_revenue = round(qty * sale_price_unit, 2) if sale_price_unit else 0.0
            # Margen — threshold Hito 8 segun nota: verde >= 20%, ambar 0-20%, rojo si negativo
            cost_share = cost_real if qty > 0 else 0.0
            if sale_revenue:
                margin = round(sale_revenue - cost_share, 2)
                margin_pct = round(margin / sale_revenue * 100, 1) if sale_revenue else 0.0
                if margin < 0:
                    state = 'red'
                elif margin_pct < 20:
                    state = 'amber'
                else:
                    state = 'green'
                # Frase autoexplicativa estilo Javi
                if margin >= 0:
                    explanation = (
                        f"Vendi a {_fmt_eur(sale_price_unit)}/u, me cuesta "
                        f"{_fmt_eur(cost_share / qty if qty else 0)}/u. "
                        f"Margen +{_fmt_eur(margin)} ({margin_pct:+.1f}%)."
                    )
                else:
                    explanation = (
                        f"Vendi a {_fmt_eur(sale_price_unit)}/u, me cuesta "
                        f"{_fmt_eur(cost_share / qty if qty else 0)}/u. "
                        f"PIERDO {_fmt_eur(abs(margin))} ({margin_pct:+.1f}%)."
                    )
            else:
                margin = 0.0
                margin_pct = 0.0
                state = 'blue'
                explanation = 'Produccion a stock — sin pedido cliente vinculado, no se calcula margen.'
            rows.append({
                'production_id': self.id,
                'move_id': m.id,
                'product_id': m.product_id.id,
                'product_name': m.product_id.display_name[:80],
                'qty_produced': qty,
                'uom_id': m.product_uom.id if m.product_uom else False,
                'lot_id': lot.id if lot else False,
                'lot_name': lot_name[:80] or (lot.name if lot else '') or '',
                'picking_id': picking.id if picking else False,
                'picking_name': picking.name if picking else '',
                'picking_state': picking_state,
                'delivery_date': delivery_date,
                'sale_order_id': (sol.order_id.id if sol else (so.id if so else False)) or False,
                'sale_order_name': (sol.order_id.name if sol else (so.name if so else '')) or '',
                'sale_partner_id': partner.id if partner else False,
                'sale_partner_name': (partner.name or '')[:60] if partner else '',
                'sale_price_unit': round(sale_price_unit, 2),
                'sale_revenue': sale_revenue,
                'cost_real_total': round(cost_share, 2),
                'margin': margin,
                'margin_pct': margin_pct,
                'state': state,
                'margin_explanation': explanation[:255],
            })
        if rows:
            Fin.create(rows)

    def _apunts_outgoing_picking_for_move(self, finished_move):
        """Encuentra el stock.picking de salida (cliente) asociado al move terminado.

        Estrategia: seguir move_dest_ids hasta un move con picking_id cuyo picking_type.code = 'outgoing'.
        Si no existe (produccion a stock pura), devuelve False.
        """
        if not finished_move:
            return False
        visited = set()
        queue = list(finished_move.move_dest_ids)
        while queue:
            m = queue.pop(0)
            if m.id in visited:
                continue
            visited.add(m.id)
            if m.picking_id and m.picking_id.picking_type_id.code == 'outgoing':
                return m.picking_id
            queue.extend(m.move_dest_ids)
            if len(visited) > 50:  # safeguard
                break
        return False

    def _apunts_revenue_total(self):
        """Ingreso total de la OF: suma de price_unit x qty para los productos
        terminados de la OF. Si no hay SO vinculada, 0.

        Hito 11: usa el helper `_apunts_get_sale_order` que respeta tanto el `sale_id`
        estandar de Odoo como el campo Studio detectado (ej. `x_studio_venta` en JR).
        """
        self.ensure_one()
        so = self._apunts_get_sale_order()
        if not so:
            return 0.0
        revenue = 0.0
        product_ids = self.move_finished_ids.product_id.ids
        for line in so.order_line:
            if line.product_id.id in product_ids:
                # Proporcional a qty de esta OF (no de la SO completa)
                # Coger qty done del move_finished correspondiente
                qty_of = sum(
                    (m.quantity if m.state == 'done' else m.product_uom_qty or 0.0)
                    for m in self.move_finished_ids
                    if m.product_id.id == line.product_id.id and m.state != 'cancel'
                )
                revenue += qty_of * (line.price_unit or 0.0)
        return round(revenue, 2)

    # ============================================================
    # CALCULOS - ALERTAS
    # ============================================================

    def _apunts_create_alert_lines(self):
        self.ensure_one()
        Alert = self.env['apunts.costes.of.alert']
        rows = []
        # MP faltante sin PO
        for m in self.move_raw_ids:
            needed = m.product_uom_qty or 0.0
            consumed = m.quantity if m.state == 'done' else 0.0
            reserved = (m.quantity or 0.0) if m.state in ('assigned', 'partially_available') else 0.0
            in_transit = self._apunts_in_transit_qty(m)
            missing = needed - consumed - reserved - in_transit
            if missing > 0.001 and self.state not in ('done', 'cancel'):
                rows.append({
                    'production_id': self.id,
                    'severity': 'red',
                    'message': f'Faltan {missing:.2f} {m.product_uom.name or ""} de {m.product_id.display_name[:40]} sin PO creada.',
                    'related_product_id': m.product_id.id,
                })
        # OT desbordada
        for wo in self.workorder_ids:
            if wo.duration_expected and wo.duration > wo.duration_expected * 1.15:
                pct = round((wo.duration - wo.duration_expected) / wo.duration_expected * 100, 1)
                rows.append({
                    'production_id': self.id,
                    'severity': 'amber',
                    'message': f'OT {wo.name[:30]} va +{pct}% en horas (umbral aviso 15%).',
                    'related_workorder_id': wo.id,
                })
        # Desviacion total
        plan_total = self.apunts_total_cost_planned or 0.0
        if plan_total:
            real_total = self.apunts_total_cost_real or 0.0
            dev = (real_total - plan_total) / plan_total * 100
            if abs(dev) > 25:
                rows.append({
                    'production_id': self.id,
                    'severity': 'red',
                    'message': f'Coste total real desviado {dev:+.1f}% vs teorico (umbral critico 25%).',
                })
            elif abs(dev) > 10:
                rows.append({
                    'production_id': self.id,
                    'severity': 'amber',
                    'message': f'Coste total real desviado {dev:+.1f}% vs teorico (umbral atencion 10%).',
                })
        # Aprovisionamiento bajo
        prov = self.apunts_provision_pct or 0.0
        if self.state not in ('done', 'cancel'):
            if prov < 50:
                rows.append({
                    'production_id': self.id,
                    'severity': 'red',
                    'message': f'Aprovisionamiento al {prov:.0f}% (critico bajo 50%).',
                })
            elif prov < 80:
                rows.append({
                    'production_id': self.id,
                    'severity': 'amber',
                    'message': f'Aprovisionamiento al {prov:.0f}% (atencion bajo 80%).',
                })
        # Hito 4 + Hito 8: alerta margen negativo / bajo (threshold 20% segun nota Javi)
        # Hito 11: helper respeta sale_id estandar y campo Studio.
        revenue = self.apunts_revenue_total or 0.0
        margin = self.apunts_margin_total or 0.0
        sale = self._apunts_get_sale_order()
        if revenue > 0 and margin < 0:
            rows.append({
                'production_id': self.id,
                'severity': 'red',
                'message': (
                    f'Margen comercial NEGATIVO: ingreso {_fmt_eur(revenue)} - '
                    f'coste real {_fmt_eur(self.apunts_total_cost_real)} = '
                    f'{_fmt_eur(margin)}. Estamos perdiendo dinero al fabricar.'
                ),
                'related_sale_order_id': sale.id if sale else False,
            })
        elif revenue > 0 and self.apunts_margin_pct < 20:
            rows.append({
                'production_id': self.id,
                'severity': 'amber',
                'message': (
                    f'Margen comercial bajo: {self.apunts_margin_pct:.1f}% '
                    f'({_fmt_eur(margin)} sobre {_fmt_eur(revenue)} de ingreso). '
                    f'Umbral aviso 20%.'
                ),
                'related_sale_order_id': sale.id if sale else False,
            })
        # Alerta MP sin standard_price (hallazgo operativo)
        for m in self.move_raw_ids:
            if m.state == 'done' and (m.product_id.standard_price or 0) <= 0:
                rows.append({
                    'production_id': self.id,
                    'severity': 'amber',
                    'message': f'Producto consumido SIN coste estandar configurado: {m.product_id.display_name[:50]}.',
                    'related_product_id': m.product_id.id,
                })
                break  # solo un aviso, no spam
        if rows:
            Alert.create(rows)

    # ============================================================
    # ACTIONS - VISTA / SMART BUTTON
    # ============================================================

    def action_apunts_open_costes(self):
        """Smart button principal: abre vista form alternativa Costes OF para esta OF."""
        self.ensure_one()
        self._apunts_regenerate_lines()
        view = self.env.ref('apunts_costes_of.view_apunts_mrp_production_form_costes')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Costes OF - {self.name}',
            'res_model': 'mrp.production',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view.id,
            'views': [(view.id, 'form')],
            'target': 'current',
        }

    def action_apunts_refresh_costes(self):
        """Boton refresh dentro de la vista costes: recalcula y mantiene vista."""
        self.ensure_one()
        self._apunts_regenerate_lines()
        return self.action_apunts_open_costes()

    def action_apunts_back_to_main(self):
        """Volver a la vista form principal nativa."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'mrp.production',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ============================================================
    # ACTIONS - DRILL-DOWN KPI CARDS
    # ============================================================

    def action_apunts_drill_material(self):
        """Click KPI Material -> stock.move filtrados por raw_material_production_id."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Movimientos de material - {self.name}',
            'res_model': 'stock.move',
            'view_mode': 'list,form,pivot,graph',
            'domain': [('raw_material_production_id', '=', self.id)],
            'target': 'current',
        }

    def action_apunts_drill_labor(self):
        """Click KPI Mano de obra -> productivity entries con employee_id."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tiempos imputados - {self.name}',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'list,pivot,graph',
            'domain': [
                ('workorder_id.production_id', '=', self.id),
                ('date_end', '!=', False),
                ('employee_id', '!=', False),
            ],
            'target': 'current',
        }

    def action_apunts_drill_operation(self):
        """Click KPI Operacion -> mrp.workorder de la OF."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Operaciones - {self.name}',
            'res_model': 'mrp.workorder',
            'view_mode': 'list,form,pivot,graph',
            'domain': [('production_id', '=', self.id)],
            'target': 'current',
        }

    def action_apunts_drill_total(self):
        """Click KPI Total -> wizard PDF Cost Analysis nativo si esta done; si no, refresh."""
        self.ensure_one()
        if self.state == 'done':
            try:
                action = self.env['ir.actions.act_window']._for_xml_id('mrp_account.action_view_mrp_cost_structure_report')
                action['context'] = {'active_ids': [self.id], 'active_model': 'mrp.production'}
                return action
            except ValueError:
                pass
        return self.action_apunts_refresh_costes()

    def action_apunts_drill_attendance(self):
        """Drill desde KPI / pestaña Asistencias → productivity entries con employee."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Asistencias - {self.name}',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'list,pivot,graph',
            'domain': [
                ('workorder_id.production_id', '=', self.id),
                ('date_end', '!=', False),
            ],
            'context': {'group_by': ['employee_id', 'date_start:day']},
            'target': 'current',
        }

    def action_apunts_drill_finished(self):
        """Drill KPI Producto terminado → stock.move de move_finished_ids."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Producto terminado - {self.name}',
            'res_model': 'stock.move',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
            'target': 'current',
        }

    def action_apunts_drill_sale(self):
        """Drill desde margen → sale.order vinculada (sale_id estandar o campo Studio)."""
        self.ensure_one()
        so = self._apunts_get_sale_order()
        if not so:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin pedido cliente',
                    'message': f'La OF {self.name} no tiene SO vinculada (produccion a stock).',
                    'sticky': False,
                    'type': 'info',
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ============================================================
    # HITO 10 - EDITOR HORAS PRODUCTIVITY (admin)
    # ============================================================

    def action_apunts_open_productivity_editor(self):
        """Editor admin de horas productivity para esta OF.

        Abre lista editable de mrp.workcenter.productivity filtrada por
        workorder_id.production_id == self.id. Permite anyadir / editar /
        borrar entries (corregir registros sucios de empleados que se equivocan).

        Solo `base.group_system` (admin pleno) — la edicion a posteriori afecta
        a costes laborales, semaforo de margen y reportes; por seguridad y
        trazabilidad limitamos a administradores.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            from odoo.exceptions import AccessError
            raise AccessError(
                'El editor de horas (productivity) es solo para administradores. '
                'Permite modificar imputaciones a posteriori (afecta a costes laborales y margen). '
                'Si necesitas corregir un registro y no eres admin, pidelo al responsable.'
            )
        first_wo = self.workorder_ids[:1]
        return {
            'type': 'ir.actions.act_window',
            'name': f'Editor horas (admin) — {self.name}',
            'res_model': 'mrp.workcenter.productivity',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('apunts_costes_of.view_apunts_productivity_editor_list').id, 'list'),
                (False, 'form'),
            ],
            'domain': [('workorder_id.production_id', '=', self.id)],
            'context': {
                'default_workorder_id': first_wo.id if first_wo else False,
                'default_workcenter_id': first_wo.workcenter_id.id if first_wo else False,
                'apunts_productivity_editor': True,
                'apunts_production_id': self.id,
            },
            'target': 'current',
        }

    def action_apunts_recalc_after_edit(self):
        """Tras editar productivity (Hito 10), invalida cache y regenera lineas auxiliares.

        El usuario admin lo dispara manualmente cuando ha terminado de corregir horas
        para que KPIs (mat_real / labor_real / oper_real / margen) reflejen los nuevos numeros.
        """
        self.ensure_one()
        self.invalidate_recordset([
            'apunts_total_cost_real', 'apunts_material_cost_real',
            'apunts_labor_cost_real', 'apunts_operation_cost_real',
            'apunts_revenue_total', 'apunts_margin_total', 'apunts_margin_pct',
        ])
        self._apunts_regenerate_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Costes recalculados',
                'message': (
                    f'KPIs y lineas auxiliares de {self.name} regenerados con la productivity '
                    f'actualizada. Si has cambiado horas a empleados con hourly_cost=0, recuerda '
                    f'corregir su master data en Master Data Costes (la edicion de horas no '
                    f'cambia el coste/hora del empleado, solo la duracion imputada).'
                ),
                'sticky': False,
                'type': 'success',
                'next': self.action_apunts_open_costes(),
            },
        }

    def action_apunts_open_desglose(self):
        """Abre modal con desglose detallado de costes (presupuestado vs real por categoría)."""
        self.ensure_one()
        mat_plan = self.apunts_material_cost_planned or 0.0
        mat_real = self.apunts_material_cost_real or 0.0
        labor_plan = self.apunts_labor_cost_planned or 0.0
        labor_real = self.apunts_labor_cost_real or 0.0
        oper_plan = self.apunts_operation_cost_planned or 0.0
        oper_real = self.apunts_operation_cost_real or 0.0
        total_plan = mat_plan + labor_plan + oper_plan
        total_real = mat_real + labor_real + oper_real
        wizard = self.env['apunts.costes.of.desglose.wizard'].create({
            'production_id': self.id,
            'material_presupuestado': mat_plan,
            'material_consumido': mat_real,
            'material_restante': max(0.0, mat_plan - mat_real),
            'labor_presupuestado': labor_plan,
            'labor_imputado': labor_real,
            'centros_presupuestado': oper_plan,
            'centros_imputado': oper_real,
            'total_presupuestado': total_plan,
            'total_actual': total_real,
            'total_restante': max(0.0, total_plan - total_real),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': f'Desglose costes — {self.name}',
            'res_model': 'apunts.costes.of.desglose.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apunts_drill_in_transit(self):
        """Click sobre POs de aprovisionamiento -> purchase.order vinculadas via procurement_group."""
        self.ensure_one()
        if not self.procurement_group_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin grupo de aprovisionamiento',
                    'message': f'La OF {self.name} no tiene procurement_group_id (no se origino via reglas de stock).',
                    'sticky': False,
                    'type': 'info',
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': f'POs vinculadas - {self.name}',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('group_id', '=', self.procurement_group_id.id)],
            'target': 'current',
        }
