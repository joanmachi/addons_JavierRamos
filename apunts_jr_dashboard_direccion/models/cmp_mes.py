"""Registro mensual de producción (el CMP de siempre).

Replica las hojas "registro por centros" y "registro por operarios" del cuadro
de producción: una fila por centro (o por operario) y mes, con las horas
trabajadas, las horas que estaban previstas y la productividad que sale de
comparar ambas.

Del cuadro antiguo se replican las columnas que Odoo puede dar con datos reales:
  · H.Máq.  → suma de fichajes (dos máquinas a la vez cuentan dos veces)
  · H.Oper. → tiempo de persona (uniendo los fichajes solapados de cada uno)
  · horas previstas → duración prevista de las órdenes terminadas
  · productividad → previstas ÷ H.Máq. (el "objetivo 1" de siempre)
  · MACOP → H.Máq. ÷ H.Oper. (objetivo 1,25)
La venta ideal/real por centro venía del programa anterior y no existe en Odoo.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


class ApuntsCmpMes(models.Model):
    _name = "apunts.cmp.mes"
    _description = "Registro mensual de producción (CMP)"
    _order = "fecha desc, tipo, nombre"
    _rec_name = "nombre"

    tipo = fields.Selection(
        [("centro", "Centro de trabajo"), ("operario", "Operario")],
        string="Tipo", required=True, index=True,
    )
    workcenter_id = fields.Many2one("mrp.workcenter", string="Centro", index=True, ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", string="Operario", index=True, ondelete="cascade")
    nombre = fields.Char(string="Nombre", index=True)

    fecha = fields.Date(string="Mes", required=True, index=True,
                        help="Primer día del mes al que corresponden las horas.")
    anio = fields.Integer(string="Año", index=True)
    mes = fields.Integer(string="Nº mes", index=True)
    mes_nombre = fields.Char(string="Mes (nombre)")

    horas_fichadas = fields.Float(string="H. Máquina", digits=(16, 2),
                                  help="Suma de todos los fichajes en órdenes: si un operario lleva "
                                       "dos máquinas a la vez, cuentan las dos. Es la H.Máq. del "
                                       "cuadro de siempre.")
    horas_operario = fields.Float(string="H. Operario", digits=(16, 2),
                                  help="Tiempo real de persona, sin contar dos veces los ratos con "
                                       "varias máquinas a la vez. Es la H.Oper. del cuadro de siempre.")
    horas_previstas = fields.Float(string="H. Previstas", digits=(16, 2),
                                   help="Horas que estaban previstas en las órdenes terminadas ese mes.")
    n_ot_terminadas = fields.Integer(string="OT terminadas")
    productividad = fields.Float(string="Productividad", digits=(16, 2),
                                 compute="_compute_productividad", store=True, aggregator="avg",
                                 help="Horas previstas ÷ horas fichadas. 1,00 = se cumple el tiempo "
                                      "previsto; más de 1 se va más rápido; menos, se tarda más.")
    dias_laborables = fields.Integer(string="Días laborables",
                                     help="Días de lunes a viernes del mes.")
    horas_dia = fields.Float(string="Horas/día", digits=(16, 2), compute="_compute_productividad",
                             store=True, aggregator="avg",
                             help="Horas fichadas entre los días laborables del mes.")
    macop = fields.Float(string="MACOP", digits=(16, 2), compute="_compute_productividad",
                         store=True, aggregator="avg",
                         help="H. Máquina ÷ H. Operario: cuántas máquinas lleva de media a la vez. "
                              "Objetivo del cuadro de siempre: 1,25.")
    objetivo_productividad = fields.Float(string="Objetivo", digits=(16, 2), default=1.0)
    cumple = fields.Boolean(string="Cumple objetivo", compute="_compute_productividad", store=True)

    _sql_constraints = [
        ("cmp_uniq", "unique(tipo, workcenter_id, employee_id, fecha)",
         "Ya existe el registro de ese centro/operario para ese mes."),
    ]

    @api.depends("horas_fichadas", "horas_previstas", "dias_laborables", "objetivo_productividad")
    def _compute_productividad(self):
        for r in self:
            r.productividad = (r.horas_previstas / r.horas_fichadas) if r.horas_fichadas else 0.0
            r.macop = (r.horas_fichadas / r.horas_operario) if r.horas_operario else 0.0
            r.horas_dia = (r.horas_fichadas / r.dias_laborables) if r.dias_laborables else 0.0
            r.cumple = r.productividad >= (r.objetivo_productividad or 1.0)

    # ── Cálculo con datos reales ──────────────────────────────────────────────

    @api.model
    def _dias_laborables(self, ini, fin):
        n, d = 0, ini
        while d <= fin:
            if d.weekday() < 5:
                n += 1
            d += timedelta(days=1)
        return n

    @api.model
    def _horas_union_por(self, campo, ini, fin_dt):
        """Horas de persona por centro u operario: une los fichajes solapados
        para no contar dos veces los ratos con varias máquinas a la vez."""
        self.env.cr.execute("""
            SELECT %s, employee_id, date_start, date_end
            FROM mrp_workcenter_productivity
            WHERE date_end IS NOT NULL AND employee_id IS NOT NULL AND %s IS NOT NULL
              AND date_end >= %%s AND date_end < %%s
            ORDER BY %s, employee_id, date_start""" % (campo, campo, campo), (ini, fin_dt))
        res = {}
        clave_actual = None
        ini_tr = fin_tr = None
        for grupo, emp, ds, de in self.env.cr.fetchall():
            k = (grupo, emp)
            if k != clave_actual:
                if ini_tr is not None:
                    res[clave_actual[0]] = res.get(clave_actual[0], 0.0) + (
                        (fin_tr - ini_tr).total_seconds() / 3600.0)
                clave_actual, ini_tr, fin_tr = k, ds, de
                continue
            if ds > fin_tr:
                res[k[0]] = res.get(k[0], 0.0) + ((fin_tr - ini_tr).total_seconds() / 3600.0)
                ini_tr, fin_tr = ds, de
            else:
                fin_tr = max(fin_tr, de)
        if ini_tr is not None:
            res[clave_actual[0]] = res.get(clave_actual[0], 0.0) + (
                (fin_tr - ini_tr).total_seconds() / 3600.0)
        return res

    @api.model
    def actualizar_mes(self, anio, mes):
        """Rehace las filas de centros y operarios de ese mes."""
        ini = date(anio, mes, 1)
        fin = (date(anio + (mes // 12), (mes % 12) + 1, 1) - timedelta(days=1))
        dias = self._dias_laborables(ini, fin)
        fin_dt = fin + timedelta(days=1)
        cr = self.env.cr

        # Horas fichadas por CENTRO y por OPERARIO en el mes
        cr.execute("""
            SELECT workcenter_id, employee_id, SUM(duration)/60.0
            FROM mrp_workcenter_productivity
            WHERE date_end IS NOT NULL AND date_end >= %s AND date_end < %s
            GROUP BY workcenter_id, employee_id""", (ini, fin_dt))
        horas_centro, horas_emp = {}, {}
        for wc, emp, h in cr.fetchall():
            if wc:
                horas_centro[wc] = horas_centro.get(wc, 0.0) + float(h or 0)
            if emp:
                horas_emp[emp] = horas_emp.get(emp, 0.0) + float(h or 0)

        # Horas previstas y nº de OT terminadas en el mes, por centro
        cr.execute("""
            SELECT workcenter_id, SUM(duration_expected)/60.0, COUNT(*)
            FROM mrp_workorder
            WHERE state='done' AND date_finished >= %s AND date_finished < %s
              AND workcenter_id IS NOT NULL
            GROUP BY workcenter_id""", (ini, fin_dt))
        prev_centro = {r[0]: (float(r[1] or 0), int(r[2] or 0)) for r in cr.fetchall()}

        # Horas previstas por OPERARIO: se reparten las de cada orden terminada
        # entre quienes ficharon en ella, en proporción a lo que fichó cada uno.
        cr.execute("""
            WITH wo_real AS (
                SELECT workorder_id, SUM(duration) AS tot
                FROM mrp_workcenter_productivity
                WHERE workorder_id IS NOT NULL AND date_end IS NOT NULL
                GROUP BY workorder_id)
            SELECT p.employee_id,
                   SUM(wo.duration_expected * (p.duration::float / NULLIF(wr.tot,0)))/60.0,
                   COUNT(DISTINCT wo.id)
            FROM mrp_workcenter_productivity p
            JOIN mrp_workorder wo ON wo.id = p.workorder_id
            JOIN wo_real wr ON wr.workorder_id = p.workorder_id
            WHERE wo.state='done' AND p.employee_id IS NOT NULL
              AND p.date_end >= %s AND p.date_end < %s
            GROUP BY p.employee_id""", (ini, fin_dt))
        prev_emp = {r[0]: (float(r[1] or 0), int(r[2] or 0)) for r in cr.fetchall()}

        oper_centro = self._horas_union_por("workcenter_id", ini, fin_dt)
        oper_emp = self._horas_union_por("employee_id", ini, fin_dt)

        WC = self.env["mrp.workcenter"].sudo().with_context(active_test=False)
        EMP = self.env["hr.employee"].sudo().with_context(active_test=False)
        creados = 0
        base = {"fecha": ini, "anio": anio, "mes": mes,
                "mes_nombre": MESES[mes - 1], "dias_laborables": dias}

        for wc_id, horas in horas_centro.items():
            prev, n_ot = prev_centro.get(wc_id, (0.0, 0))
            creados += self._guardar(dict(base, tipo="centro", workcenter_id=wc_id,
                                          nombre=WC.browse(wc_id).name or "",
                                          horas_fichadas=horas,
                                          horas_operario=oper_centro.get(wc_id, 0.0),
                                          horas_previstas=prev,
                                          n_ot_terminadas=n_ot),
                                     [("tipo", "=", "centro"), ("workcenter_id", "=", wc_id)])
        for emp_id, horas in horas_emp.items():
            prev, n_ot = prev_emp.get(emp_id, (0.0, 0))
            creados += self._guardar(dict(base, tipo="operario", employee_id=emp_id,
                                          nombre=EMP.browse(emp_id).name or "",
                                          horas_fichadas=horas,
                                          horas_operario=oper_emp.get(emp_id, 0.0),
                                          horas_previstas=prev,
                                          n_ot_terminadas=n_ot),
                                     [("tipo", "=", "operario"), ("employee_id", "=", emp_id)])
        return creados

    def _guardar(self, vals, dominio):
        rec = self.search(dominio + [("fecha", "=", vals["fecha"])], limit=1)
        if rec:
            rec.write(vals)
        else:
            self.create(vals)
        return 1

    @api.model
    def reconstruir_historico(self, anio=None):
        """Rehace todos los meses del año con lo que hay fichado."""
        hoy = fields.Date.context_today(self)
        anio = anio or hoy.year
        n = 0
        for mes in range(1, 13):
            if date(anio, mes, 1) > hoy:
                break
            n += self.actualizar_mes(anio, mes)
        _logger.info("CMP: %s filas de producción reconstruidas para %s", n, anio)
        return n

    @api.model
    def cron_mes(self):
        """Rehace el mes en curso y el anterior."""
        hoy = fields.Date.context_today(self)
        self.actualizar_mes(hoy.year, hoy.month)
        ant = hoy.replace(day=1) - timedelta(days=1)
        self.actualizar_mes(ant.year, ant.month)
