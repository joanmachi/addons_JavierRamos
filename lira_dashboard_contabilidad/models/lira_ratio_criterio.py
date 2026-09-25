# -*- coding: utf-8 -*-
"""Criterios de aceptación de los ratios del Dashboard, editables.

Los semáforos de los ratios (verde / amarillo / rojo) usaban umbrales genéricos
de manual, iguales para cualquier empresa. El cliente trabaja en un sector con
mucha inversión en maquinaria y facturación que oscila según el peso de la
materia prima en cada proyecto, así que sus valores razonables no son los del
libro. Aquí cada ratio tiene su umbral, editable por la empresa: cuando su
asesor financiero fije los valores del sector, se teclean y listo.
"""
from odoo import api, fields, models

# (clave, nombre visible, verde por defecto, amarillo por defecto, sentido)
CRITERIOS_DEFECTO = [
    ("liquidez", "Liquidez general", 1.5, 1.0, "mayor"),
    ("liq_inmediata", "Liquidez inmediata", 1.0, 0.75, "mayor"),
    ("tesoreria", "Tesorería", 0.3, 0.1, "mayor"),
    ("solvencia", "Solvencia", 2.0, 1.0, "mayor"),
    ("endeudamiento", "Endeudamiento (%)", 50.0, 70.0, "menor"),
    ("roe", "ROE (%)", 10.0, 0.0, "mayor"),
    ("roa", "ROA (%)", 5.0, 0.0, "mayor"),
    ("ebitda", "EBITDA (%)", 15.0, 5.0, "mayor"),
    ("margen_neto", "Margen neto (%)", 10.0, 0.0, "mayor"),
    ("edv", "EDV — Estructura s/ ventas (%)", 8.0, 12.5, "menor"),
    ("cov", "COV — Coste operativo s/ ventas (%)", 80.0, 90.0, "menor"),
]


class LiraRatioCriterio(models.Model):
    _name = "lira.ratio.criterio"
    _description = "Criterio de aceptación de un ratio del Dashboard"
    _order = "secuencia, id"

    clave = fields.Char(string="Clave técnica", required=True, index=True)
    name = fields.Char(string="Ratio", required=True)
    secuencia = fields.Integer(string="Orden", default=10)
    verde = fields.Float(string="Verde desde", digits=(16, 2),
                         help="El ratio sale en verde a partir de este valor "
                              "(o por debajo, si es de los que cuanto menos mejor).")
    amarillo = fields.Float(string="Amarillo desde", digits=(16, 2),
                            help="Entre este valor y el verde, el ratio sale en amarillo. "
                                 "Fuera de los dos, en rojo.")
    sentido = fields.Selection([("mayor", "Cuanto más, mejor"), ("menor", "Cuanto menos, mejor")],
                               string="Sentido", default="mayor", required=True)
    notas = fields.Char(string="Origen / notas",
                        help="De dónde sale este criterio (asesor, sector, manual...).")
    relativo_a = fields.Char(string="Relativo a",
                             help="Si se rellena, el semáforo no mira el valor sino la DIFERENCIA "
                                  "con ese otro KPI. Ej.: el periodo de pago se compara con el de "
                                  "cobro: verde si paga 5 días más tarde de lo que cobra.")
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    _sql_constraints = [
        ("clave_company_uniq", "unique(clave, company_id)",
         "Ya existe un criterio para ese ratio en esta empresa."),
    ]

    @api.model
    def criterio(self, clave):
        """Devuelve (verde, amarillo, sentido) del ratio: lo configurado o, si
        la empresa no lo ha tocado, el valor genérico de siempre."""
        rec = self.search([("clave", "=", clave),
                           ("company_id", "in", (self.env.company.id, False))], limit=1)
        if rec:
            return rec.verde, rec.amarillo, rec.sentido
        for k, _n, verde, amarillo, sentido in CRITERIOS_DEFECTO:
            if k == clave:
                return verde, amarillo, sentido
        return None, None, "mayor"

    @api.model
    def evaluar(self, clave, valor, otros=None):
        """Semáforo de un valor: 'green' / 'yellow' / 'red', o 'grey' si el KPI
        no tiene criterio o no hay valor. `otros` es un dict clave→valor para
        los criterios relativos (p. ej. PMP respecto a PMC)."""
        if valor is None:
            return "grey"
        rec = self.search([("clave", "=", clave),
                           ("company_id", "in", (self.env.company.id, False))], limit=1)
        verde, amarillo, sentido = self.criterio(clave)
        if verde is None:
            return "grey"
        if rec and rec.relativo_a:
            base = (otros or {}).get(rec.relativo_a)
            if base is None:
                return "grey"
            valor = valor - base
        if sentido == "menor":
            if valor <= verde:
                return "green"
            return "yellow" if valor <= amarillo else "red"
        if valor >= verde:
            return "green"
        return "yellow" if valor >= amarillo else "red"

    def write(self, vals):
        res = super().write(vals)
        # Las bandas dibujadas en las gráficas del panel se regeneran con el criterio nuevo
        if self.env.get("apunts.kpi.serie") is not None and \
           {"verde", "amarillo", "sentido", "relativo_a"} & set(vals):
            for rec in self:
                try:
                    self.env["apunts.kpi.serie"]._regenerar(rec.clave)
                except Exception:
                    pass
        return res

    @api.model
    def action_open(self):
        """Abre la lista, creando antes las filas que falten con los valores
        genéricos, para que la empresa vea qué está en juego y edite encima."""
        existentes = set(self.search([]).mapped("clave"))
        for i, (clave, nombre, verde, amarillo, sentido) in enumerate(CRITERIOS_DEFECTO):
            if clave not in existentes:
                self.create({"clave": clave, "name": nombre, "secuencia": (i + 1) * 10,
                             "verde": verde, "amarillo": amarillo, "sentido": sentido,
                             "notas": "Criterio genérico inicial"})
        return {
            "type": "ir.actions.act_window",
            "name": "Criterios de aceptación de los ratios",
            "res_model": "lira.ratio.criterio",
            "view_mode": "list",
            "views": [[False, "list"]],
            "target": "current",
        }
