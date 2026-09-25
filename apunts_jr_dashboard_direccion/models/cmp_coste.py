"""Precio por hora del taller (hoja "registro P.Hora" del cuadro de producción).

Reparte el gasto del taller en categorías y lo divide entre las horas trabajadas,
para saber cuánto cuesta una hora y cuál es el punto muerto: por debajo de ese
precio, la hora se trabaja a pérdida.

Cada categoría se alimenta de dos sitios, y se configuran a mano sin tocar código:
  · CUENTAS CONTABLES: lo que se ha gastado de verdad (herramienta, electricidad,
    amortizaciones, personal...).
  · CENTROS DE TRABAJO: horas fichadas en un centro × su precio por hora. Es como
    lo hacía el cuadro antiguo con logística o mantenimiento.
Si una categoría no tiene ni cuentas ni centros, se puede escribir el importe a mano.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApuntsCmpCosteCategoria(models.Model):
    _name = "apunts.cmp.coste.categoria"
    _description = "Categoría de coste del taller"
    _order = "secuencia, name"

    name = fields.Char(string="Categoría", required=True)
    secuencia = fields.Integer(string="Orden", default=10)
    tipo = fields.Selection(
        [("directo", "Coste directo de fabricación"), ("gasto", "Gasto de estructura")],
        string="Tipo", required=True, default="directo",
        help="En el cuadro antiguo los directos eran las columnas B a J y los gastos las K a O.",
    )
    account_ids = fields.Many2many("account.account", string="Cuentas contables",
                                   help="El gasto de estas cuentas se imputa a esta categoría.")
    workcenter_ids = fields.Many2many("mrp.workcenter", string="Centros de trabajo",
                                      help="Las horas fichadas en estos centros se valoran a la "
                                           "tarifa de abajo y se suman a esta categoría.")
    tarifa_hora = fields.Float(string="Precio por hora del centro", digits=(16, 2),
                               help="Lo que cuesta una hora en esos centros. En el cuadro antiguo "
                                    "eran 29 €/h mantenimiento, 28 €/h las acciones 5S y 23 €/h logística.")
    cuenta_icap = fields.Boolean(string="Entra en el ICAP", default=False,
                                 help="El ICAP era el índice de costes auxiliares: lo que se puede "
                                      "controlar (herramienta, consumibles, reparaciones, 5S...).")
    activo = fields.Boolean(string="Activa", default=True)


class ApuntsCmpCoste(models.Model):
    _name = "apunts.cmp.coste"
    _description = "Coste del taller por mes y categoría (CMP)"
    _order = "fecha desc, categoria_id"

    fecha = fields.Date(string="Mes", required=True, index=True)
    anio = fields.Integer(string="Año", index=True)
    mes = fields.Integer(string="Nº mes", index=True)
    categoria_id = fields.Many2one("apunts.cmp.coste.categoria", string="Categoría",
                                   required=True, ondelete="cascade", index=True)
    tipo = fields.Selection(related="categoria_id.tipo", store=True, string="Tipo")
    importe_cuentas = fields.Float(string="Gasto contable", digits=(16, 2))
    horas_centro = fields.Float(string="Horas de centros", digits=(16, 2))
    importe_horas = fields.Float(string="Coste de esas horas", digits=(16, 2))
    importe = fields.Float(string="Importe total", digits=(16, 2), compute="_compute_importe",
                           store=True)
    horas_taller = fields.Float(string="Horas del taller", digits=(16, 2),
                                help="Horas fichadas en todo el taller ese mes: es el divisor.")
    coste_hora = fields.Float(string="Coste por hora", digits=(16, 3), compute="_compute_importe",
                              store=True, help="Lo que aporta esta categoría al precio de la hora.")

    _sql_constraints = [("coste_uniq", "unique(fecha, categoria_id)",
                         "Ya existe esa categoría para ese mes.")]

    @api.depends("importe_cuentas", "importe_horas", "horas_taller")
    def _compute_importe(self):
        for r in self:
            r.importe = r.importe_cuentas + r.importe_horas
            r.coste_hora = (r.importe / r.horas_taller) if r.horas_taller else 0.0

    # ── Cálculo con datos reales ──────────────────────────────────────────────

    @api.model
    def actualizar_mes(self, anio, mes):
        ini = date(anio, mes, 1)
        fin = date(anio + (mes // 12), (mes % 12) + 1, 1) - timedelta(days=1)
        fin_dt = fin + timedelta(days=1)
        cid = self.env.company.id
        cr = self.env.cr

        # Horas de todo el taller ese mes (el divisor del precio por hora)
        cr.execute("""SELECT COALESCE(SUM(duration),0)/60.0 FROM mrp_workcenter_productivity
                      WHERE date_end IS NOT NULL AND date_end >= %s AND date_end < %s""",
                   (ini, fin_dt))
        horas_taller = float(cr.fetchone()[0] or 0)

        n = 0
        for cat in self.env["apunts.cmp.coste.categoria"].search([("activo", "=", True)]):
            importe_cuentas = 0.0
            if cat.account_ids:
                cr.execute("""SELECT COALESCE(SUM(balance), 0) FROM account_move_line
                              WHERE parent_state='posted' AND company_id=%s
                                AND date >= %s AND date <= %s AND account_id IN %s""",
                           (cid, ini, fin, tuple(cat.account_ids.ids)))
                importe_cuentas = float(cr.fetchone()[0] or 0)
            horas_centro = 0.0
            if cat.workcenter_ids:
                cr.execute("""SELECT COALESCE(SUM(duration),0)/60.0
                              FROM mrp_workcenter_productivity
                              WHERE date_end IS NOT NULL AND date_end >= %s AND date_end < %s
                                AND workcenter_id IN %s""",
                           (ini, fin_dt, tuple(cat.workcenter_ids.ids)))
                horas_centro = float(cr.fetchone()[0] or 0)
            importe_horas = horas_centro * (cat.tarifa_hora or 0.0)
            if not importe_cuentas and not importe_horas:
                continue
            vals = {"fecha": ini, "anio": anio, "mes": mes, "categoria_id": cat.id,
                    "importe_cuentas": importe_cuentas, "horas_centro": horas_centro,
                    "importe_horas": importe_horas, "horas_taller": horas_taller}
            rec = self.search([("fecha", "=", ini), ("categoria_id", "=", cat.id)], limit=1)
            rec.write(vals) if rec else self.create(vals)
            n += 1
        return n

    @api.model
    def reconstruir_historico(self, anio=None):
        hoy = fields.Date.context_today(self)
        anio = anio or hoy.year
        n = 0
        for mes in range(1, 13):
            if date(anio, mes, 1) > hoy:
                break
            n += self.actualizar_mes(anio, mes)
        _logger.info("CMP coste/hora: %s filas para %s", n, anio)
        return n

    @api.model
    def cron_mes(self):
        hoy = fields.Date.context_today(self)
        self.actualizar_mes(hoy.year, hoy.month)
        ant = hoy.replace(day=1) - timedelta(days=1)
        self.actualizar_mes(ant.year, ant.month)
