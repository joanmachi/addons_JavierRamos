"""Portada del cuadro de producción: los índices de la hoja " grafica 1"
y la previsión de horas de la hoja "seguimiento horario".

Las definiciones son las que dejó escritas el autor del Excel en los
comentarios de sus celdas:
  · MACPRE = horas máquina ÷ horas de presencia
  · MACOP  = horas máquina ÷ horas facturables (las que el operario está en OFs)
  · productividad = lo previsto ÷ lo que de verdad se ha tardado

La diferencia entre hora-máquina y hora-operario existe porque un operario
puede tener varias máquinas en marcha a la vez: la hora-máquina las suma todas,
la hora-operario cuenta el tiempo una sola vez.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

DIAS_ANO = 226  # días laborables de un año, como en el cuadro antiguo


class ApuntsCmpIndicador(models.Model):
    _name = "apunts.cmp.indicador"
    _description = "Índices del cuadro de producción (CMP)"
    _order = "fecha desc"

    fecha = fields.Date(string="Semana (lunes)", required=True, index=True)
    semana = fields.Integer(string="Nº semana", index=True)
    anio = fields.Integer(string="Año", index=True)

    horas_maquina = fields.Float(string="Horas máquina", digits=(16, 2),
                                 help="Suma de todos los fichajes en órdenes. Si un operario tiene "
                                      "dos máquinas a la vez, cuentan las dos.")
    horas_operario = fields.Float(string="Horas operario", digits=(16, 2),
                                  help="Tiempo real del operario en órdenes, sin contar dos veces "
                                       "los ratos en que llevaba varias máquinas.")
    horas_presencia = fields.Float(string="Horas de presencia", digits=(16, 2),
                                   help="Horas de fábrica según las asistencias.")
    horas_previstas = fields.Float(string="Horas previstas", digits=(16, 2))

    macop = fields.Float(string="MACOP", digits=(16, 3), compute="_compute_indices", store=True,
                         help="Horas máquina ÷ horas del operario en órdenes. Cuántas máquinas "
                              "lleva de media cada operario. Objetivo del cuadro: 1,25.")
    macpre = fields.Float(string="MACPRE", digits=(16, 3), compute="_compute_indices", store=True,
                          help="Horas máquina ÷ horas de presencia. Cuánto de la jornada se "
                               "convierte en máquina en marcha. Objetivo del cuadro: 1,125.")
    productividad = fields.Float(string="Productividad", digits=(16, 3), compute="_compute_indices",
                                 store=True, help="Horas previstas ÷ horas máquina. Objetivo: 1,00.")
    horas_acumuladas = fields.Float(string="Horas acumuladas del año", digits=(16, 2))
    dias_transcurridos = fields.Integer(string="Días laborables transcurridos")
    prevision_anual = fields.Float(string="Previsión de horas del año", digits=(16, 2),
                                   compute="_compute_indices", store=True,
                                   help="Al ritmo llevado: horas acumuladas ÷ días transcurridos × "
                                        "%d días. Es la hoja de seguimiento horario." % DIAS_ANO)

    _sql_constraints = [("cmp_ind_uniq", "unique(fecha)", "Ya existe esa semana.")]

    @api.depends("horas_maquina", "horas_operario", "horas_presencia",
                 "horas_previstas", "horas_acumuladas", "dias_transcurridos")
    def _compute_indices(self):
        for r in self:
            r.macop = (r.horas_maquina / r.horas_operario) if r.horas_operario else 0.0
            r.macpre = (r.horas_maquina / r.horas_presencia) if r.horas_presencia else 0.0
            r.productividad = (r.horas_previstas / r.horas_maquina) if r.horas_maquina else 0.0
            r.prevision_anual = ((r.horas_acumuladas / r.dias_transcurridos * DIAS_ANO)
                                 if r.dias_transcurridos else 0.0)

    # ── Cálculo ───────────────────────────────────────────────────────────────

    @api.model
    def _horas_operario_union(self, ini, fin):
        """Horas del operario SIN contar dos veces los ratos con varias máquinas.

        Se unen los intervalos solapados de cada operario: si de 8 a 10 lleva
        dos máquinas, son 2 horas de operario y 4 de máquina."""
        self.env.cr.execute("""
            SELECT employee_id, date_start, date_end
            FROM mrp_workcenter_productivity
            WHERE date_end IS NOT NULL AND employee_id IS NOT NULL
              AND date_end >= %s AND date_end < %s
            ORDER BY employee_id, date_start""", (ini, fin))
        total, actual_emp, fin_actual, ini_actual = 0.0, None, None, None
        for emp, ds, de in self.env.cr.fetchall():
            if emp != actual_emp:
                if ini_actual:
                    total += (fin_actual - ini_actual).total_seconds()
                actual_emp, ini_actual, fin_actual = emp, ds, de
                continue
            if ds > fin_actual:                 # hueco: cierra el tramo anterior
                total += (fin_actual - ini_actual).total_seconds()
                ini_actual, fin_actual = ds, de
            else:                                # solapa: se alarga el tramo
                fin_actual = max(fin_actual, de)
        if ini_actual:
            total += (fin_actual - ini_actual).total_seconds()
        return total / 3600.0

    @api.model
    def actualizar_semana(self, lunes):
        domingo = lunes + timedelta(days=6)
        fin_dt = domingo + timedelta(days=1)
        cr = self.env.cr

        cr.execute("""SELECT COALESCE(SUM(duration),0)/60.0 FROM mrp_workcenter_productivity
                      WHERE date_end IS NOT NULL AND date_end >= %s AND date_end < %s""",
                   (lunes, fin_dt))
        h_maquina = float(cr.fetchone()[0] or 0)
        h_operario = self._horas_operario_union(lunes, fin_dt)

        # Presencia: se descartan las asistencias absurdas (sin cerrar o de más
        # de 16 h), que son las que ensucian el dato.
        cr.execute("""SELECT COALESCE(SUM(worked_hours),0) FROM hr_attendance
                      WHERE check_out IS NOT NULL AND worked_hours <= 16
                        AND check_in >= %s AND check_in < %s""", (lunes, fin_dt))
        h_presencia = float(cr.fetchone()[0] or 0)

        cr.execute("""SELECT COALESCE(SUM(duration_expected),0)/60.0 FROM mrp_workorder
                      WHERE state='done' AND date_finished >= %s AND date_finished < %s""",
                   (lunes, fin_dt))
        h_previstas = float(cr.fetchone()[0] or 0)

        ini_ano = date(lunes.year, 1, 1)
        cr.execute("""SELECT COALESCE(SUM(duration),0)/60.0 FROM mrp_workcenter_productivity
                      WHERE date_end IS NOT NULL AND date_end >= %s AND date_end < %s""",
                   (ini_ano, fin_dt))
        h_acum = float(cr.fetchone()[0] or 0)
        # Días transcurridos en la MISMA base que los 226 del año (el Excel
        # descuenta festivos): se prorratea el calendario laboral, no los L-V.
        dias_lv, d = 0, ini_ano
        while d <= domingo:
            if d.weekday() < 5:
                dias_lv += 1
            d += timedelta(days=1)
        dias = round(dias_lv * DIAS_ANO / 261.0)

        iso = lunes.isocalendar()
        vals = {"fecha": lunes, "semana": iso[1], "anio": iso[0],
                "horas_maquina": h_maquina, "horas_operario": h_operario,
                "horas_presencia": h_presencia, "horas_previstas": h_previstas,
                "horas_acumuladas": h_acum, "dias_transcurridos": dias}
        rec = self.search([("fecha", "=", lunes)], limit=1)
        rec.write(vals) if rec else self.create(vals)
        return rec or self.search([("fecha", "=", lunes)], limit=1)

    @api.model
    def reconstruir_historico(self, anio=None):
        hoy = fields.Date.context_today(self)
        anio = anio or hoy.year
        ini = date(anio, 1, 1)
        lunes = ini - timedelta(days=ini.weekday())
        n = 0
        while lunes <= hoy:
            self.actualizar_semana(lunes)
            lunes += timedelta(days=7)
            n += 1
        _logger.info("CMP índices: %s semanas", n)
        return n

    @api.model
    def cron_semana(self):
        hoy = fields.Date.context_today(self)
        lunes = hoy - timedelta(days=hoy.weekday())
        self.actualizar_semana(lunes - timedelta(days=7))
        self.actualizar_semana(lunes)
