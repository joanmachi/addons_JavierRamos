"""Histórico semanal de los KPIs de Dirección y sus series para las gráficas.

  · apunts.kpi.semana → un valor por KPI y semana ISO. Al cerrar la semana la
    fila queda BLOQUEADA: la reunión del lunes trabaja con un dato que no
    cambia después, aunque la contabilidad se corrija.
  · apunts.kpi.serie  → la misma información desplegada en varias líneas por
    KPI (valor, media móvil de 4 semanas, límites del semáforo, misma semana
    del año anterior, acumulado del año) para que la gráfica las pinte juntas.
    Se regenera sola; no es un dato, es una vista precalculada.
"""

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .kpi_catalogo import CSS_BADGE, CSS_BORDE, ESTADO_TXT

ESTADOS = [("green", "Bien"), ("yellow", "Vigilar"), ("red", "Mal"), ("grey", "Sin objetivo")]


class ApuntsKpiSemana(models.Model):
    _name = "apunts.kpi.semana"
    _description = "KPI de Dirección — valor semanal"
    _order = "fecha desc, kpi_id"
    _rec_name = "display_name"

    kpi_id = fields.Many2one("apunts.kpi", string="KPI", required=True, index=True,
                             ondelete="cascade")
    clave = fields.Char(string="Clave", required=True, index=True)
    bloque_id = fields.Many2one(related="kpi_id.bloque_id", store=True, string="Indicador")
    fecha = fields.Date(string="Semana (lunes)", required=True, index=True)
    semana = fields.Integer(string="Nº semana", index=True)
    anio = fields.Integer(string="Año", index=True)
    valor = fields.Float(string="Valor", digits=(16, 2))
    objetivo = fields.Float(string="Objetivo", digits=(16, 2),
                            help="El límite verde vigente cuando se guardó la semana.")
    estado = fields.Selection(ESTADOS, string="Estado", default="grey")
    cerrada = fields.Boolean(string="Semana cerrada", default=False, index=True,
                             help="Una semana cerrada no se recalcula: es el dato de la reunión.")
    reconstruido = fields.Boolean(string="Reconstruido", default=False,
                                  help="Calculado hacia atrás al instalar, no en el cierre real.")
    fecha_cierre = fields.Datetime(string="Cerrada el")
    # Para pintar las tarjetas por semanas (Consultar otra semana con un rango)
    principal = fields.Boolean(related="kpi_id.principal", string="KPI principal del indicador")
    bloque_orden = fields.Integer(related="kpi_id.bloque_id.orden", string="Orden del indicador")
    kpi_orden = fields.Integer(related="kpi_id.orden", string="Orden del KPI")
    valor_txt = fields.Char(compute="_compute_tarjeta")
    objetivo_txt = fields.Char(compute="_compute_tarjeta")
    estado_txt = fields.Char(compute="_compute_tarjeta")
    css_borde = fields.Char(compute="_compute_tarjeta")
    css_badge = fields.Char(compute="_compute_tarjeta")
    semana_txt = fields.Char(compute="_compute_tarjeta")

    _sql_constraints = [
        ("kpi_fecha_uniq", "unique(kpi_id, fecha)", "Ya existe el valor de ese KPI para esa semana."),
    ]

    @api.depends("valor", "objetivo", "estado", "kpi_id", "semana", "anio", "cerrada")
    def _compute_tarjeta(self):
        for r in self:
            k = r.kpi_id
            r.valor_txt = k._fmt(r.valor) if k else ""
            r.objetivo_txt = k.objetivo_txt if k else ""
            r.estado_txt = ESTADO_TXT.get(r.estado, "")
            r.css_borde = CSS_BORDE.get(r.estado, "border-secondary")
            r.css_badge = CSS_BADGE.get(r.estado, "text-bg-secondary")
            r.semana_txt = "S%02d/%s · %s" % (r.semana or 0, r.anio or "", "cerrada" if r.cerrada else "en curso")

    @api.depends("clave", "semana", "anio")
    def _compute_display_name(self):
        for r in self:
            r.display_name = "%s · S%02d/%s" % (r.kpi_id.name or r.clave, r.semana or 0, r.anio or "")

    def write(self, vals):
        if not self.env.context.get("apunts_kpi_forzar") and \
                any(k in vals for k in ("valor", "fecha", "kpi_id", "cerrada")):
            if any(r.cerrada for r in self):
                raise UserError(
                    "Esa semana ya está cerrada: el dato de la reunión no se modifica. "
                    "Si de verdad hay que rehacerla, hay que hacerlo desde el motor de KPIs.")
        return super().write(vals)


SERIES = [
    ("valor", "Valor"),
    ("media4", "Media móvil 4 semanas"),
    ("verde", "Límite verde"),
    ("amarillo", "Límite amarillo"),
    ("ano_anterior", "Misma semana año anterior"),
    ("acumulado", "Acumulado del año"),
    ("objetivo_acumulado", "Objetivo acumulado"),
]


class ApuntsKpiSerie(models.Model):
    _name = "apunts.kpi.serie"
    _description = "KPI de Dirección — series para la gráfica"
    _order = "fecha, serie"

    kpi_id = fields.Many2one("apunts.kpi", string="KPI", required=True, index=True,
                             ondelete="cascade")
    clave = fields.Char(string="Clave", required=True, index=True)
    fecha = fields.Date(string="Semana (lunes)", required=True, index=True)
    semana = fields.Integer(string="Nº semana")
    anio = fields.Integer(string="Año")
    serie = fields.Selection(SERIES, string="Serie", required=True, index=True)
    valor = fields.Float(string="Valor", digits=(16, 2))

    @api.model
    def _regenerar(self, clave):
        """Vuelve a construir todas las líneas de la gráfica de un KPI."""
        kpi = self.env["apunts.kpi"].sudo().search([("clave", "=", clave)], limit=1)
        if not kpi:
            return 0
        self.sudo().search([("clave", "=", clave)]).unlink()
        filas = self.env["apunts.kpi.semana"].sudo().search(
            [("clave", "=", clave)], order="fecha")
        if not filas:
            return 0
        verde, amarillo, sentido = self.env["lira.ratio.criterio"].sudo().criterio(clave)
        relativo = self.env["lira.ratio.criterio"].sudo().search(
            [("clave", "=", clave)], limit=1).relativo_a
        por_semana = {(f.anio, f.semana): f.valor for f in filas}
        nuevas = []
        ventana, acumulado = [], 0.0
        anio_acum = None
        for i, f in enumerate(filas):
            base = {"kpi_id": kpi.id, "clave": clave, "fecha": f.fecha,
                    "semana": f.semana, "anio": f.anio}
            nuevas.append(dict(base, serie="valor", valor=f.valor))
            if kpi.media_movil:
                ventana.append(f.valor)
                ventana = ventana[-4:]
                nuevas.append(dict(base, serie="media4", valor=sum(ventana) / len(ventana)))
            if verde is not None and not relativo:
                nuevas.append(dict(base, serie="verde", valor=verde))
                if amarillo is not None:
                    nuevas.append(dict(base, serie="amarillo", valor=amarillo))
            anterior = por_semana.get((f.anio - 1, f.semana))
            if anterior is not None:
                nuevas.append(dict(base, serie="ano_anterior", valor=anterior))
            if kpi.tipo == "eur" and kpi.flujo:
                if anio_acum != f.anio:
                    anio_acum, acumulado, n_sem = f.anio, 0.0, 0
                acumulado += f.valor
                n_sem += 1
                nuevas.append(dict(base, serie="acumulado", valor=acumulado))
                if verde:
                    nuevas.append(dict(base, serie="objetivo_acumulado", valor=verde * n_sem))
        self.sudo().create(nuevas)
        return len(nuevas)

    @api.model
    def _regenerar_todo(self):
        n = 0
        for kpi in self.env["apunts.kpi"].sudo().search([]):
            n += self._regenerar(kpi.clave)
        return n
