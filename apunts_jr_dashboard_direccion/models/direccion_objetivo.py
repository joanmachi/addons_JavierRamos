"""Objetivos del cuadro de mando (los del CMI/CMP de siempre), editables.

El cuadro antiguo tenía una hoja de objetivos por indicador (facturación
40.000 €/semana, productividad 1, cartera 300.000 € a 3 meses...). Aquí viven
esos objetivos para poder comparar el dato real con la meta y ver el % de
cumplimiento en el Panel Dirección. Dirección los edita cuando quiera.
"""

from odoo import api, fields, models

# KPIs que admiten objetivo. La clave coincide con el campo del Panel Dirección.
KPIS_OBJETIVO = [
    ("fact_anual", "Facturación del año"),
    ("fact_semana", "Facturación semanal"),
    ("pedidos_anual", "Pedidos del año"),
    ("cartera_pendiente", "Cartera pendiente"),
    ("ebitda_pct", "EBITDA (%)"),
    ("tesoreria", "Tesorería"),
    ("cobros_pendientes", "Cobros pendientes"),
    ("cobertura_meses", "Cobertura (meses)"),
    ("horas_prod_pct", "Jornada cumplida (%)"),
    ("entregas_anual_pct", "Entregas en fecha (%)"),
    ("wip_valor", "Fabricación en curso (WIP)"),
]

BLOQUES = [
    ("cme", "CME · Económico"),
    ("cmv", "CMV · Ventas y cartera"),
    ("cml", "CML · Liquidez"),
    ("cmp", "CMP · Producción"),
]


class ApuntsDireccionObjetivo(models.Model):
    _name = "apunts.direccion.objetivo"
    _description = "Objetivo de un KPI del cuadro de mando"
    _order = "bloque, kpi"

    kpi = fields.Selection(KPIS_OBJETIVO, string="Indicador", required=True, index=True)
    bloque = fields.Selection(BLOQUES, string="Bloque", required=True, default="cme")
    valor = fields.Float(string="Objetivo", digits=(16, 2), required=True,
                         help="Meta para este indicador. En € para los importes, en % para "
                              "los porcentajes, en meses para la cobertura.")
    mejor_es_mayor = fields.Boolean(
        string="Cuanto más, mejor", default=True,
        help="Marcado: se cumple superando el objetivo (facturación, margen...). "
             "Sin marcar: se cumple quedando por debajo (cobros pendientes).",
    )
    prorratear = fields.Boolean(
        string="Prorratear por el año transcurrido", default=False,
        help="Para objetivos anuales acumulativos (facturación, pedidos): a 3 de "
             "septiembre se compara con la parte del objetivo que tocaría a esa "
             "fecha, no con el objetivo del año entero.",
    )
    notas = fields.Char(string="Origen / notas")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("kpi_uniq", "unique(kpi)", "Ya hay un objetivo para ese indicador."),
    ]

    @api.depends("kpi")
    def _compute_display_name(self):
        etiquetas = dict(KPIS_OBJETIVO)
        for rec in self:
            rec.display_name = etiquetas.get(rec.kpi, rec.kpi or "")
