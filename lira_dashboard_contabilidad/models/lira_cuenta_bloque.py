# -*- coding: utf-8 -*-
"""Clasificación de costes por bloques (la del asesor de Javier Ramos).

Sustituye al viejo reparto fijo/variable de dos montones: cada cuenta de gasto
pertenece a uno de los cuatro bloques que definió la empresa con su asesor
(septiembre de 2026), y el P&G, el margen del Panel Dirección y la evolución de
costes se calculan con esta clasificación. Es editable: si el asesor cambia el
criterio de una cuenta, se cambia aquí y todo lo demás lo recoge.
"""
from odoo import api, fields, models

BLOQUES = [
    ("variables_directos", "Variables directos"),
    ("semivariables", "Semivariables"),
    ("fijos_operativos", "Fijos operativos"),
    ("estructura", "Estructura / Dirección"),
]

# Clasificación entregada por la empresa (Clasificacion_Costes_JR_2026_v3.xlsx)
SEED = [
    ("600000020", "variables_directos", "Consumo directamente ligado a trabajos de soldadura."),
    ("601000005", "variables_directos", "Materia prima directamente incorporada al trabajo vendido."),
    ("601000006", "variables_directos", "Materia prima directamente incorporada al trabajo vendido."),
    ("601000007", "variables_directos", "Compra asociada directamente a trabajos/OF."),
    ("607000001", "variables_directos", "Subcontratación directamente vinculada a producción."),
    ("607000002", "variables_directos", "Subcontratación directamente vinculada a producción."),
    ("607000003", "variables_directos", "Tratamiento externo directamente ligado a piezas."),
    ("607000008", "variables_directos", "Transporte directo asociado a operaciones/pedidos."),
    ("607000009", "variables_directos", "Porte ligado a compras productivas."),
    ("607000011", "variables_directos", "Servicio externo directamente ligado a producción."),
    ("600000014", "semivariables", "Crece con la actividad, pero no de forma proporcional a cada venta."),
    ("600000016", "semivariables", "Herramienta/consumo condicionado por actividad y reposición."),
    ("600000017", "semivariables", "Herramienta productiva con compras irregulares."),
    ("600000018", "semivariables", "Herramienta productiva con compras irregulares."),
    ("600000019", "semivariables", "Consumo de taller relacionado con uso de máquinas."),
    ("622000001", "semivariables", "Necesario para operar, pero irregular y no proporcional a ventas."),
    ("622000002", "semivariables", "Condicionado por uso, con fuerte irregularidad temporal."),
    ("622000003", "semivariables", "Condicionado por uso de equipos, pero irregular."),
    ("628000001", "semivariables", "Tiene componente fijo y componente ligado a horas de máquina."),
    ("628000008", "semivariables", "Relacionado con nivel de actividad logística."),
    ("628000009", "semivariables", "Variable con desplazamientos/actividad."),
    ("628000088", "semivariables", "Relacionado con uso de vehículos."),
    ("628000888", "semivariables", "Relacionado con uso de vehículos."),
    ("640000001", "fijos_operativos", "Plantilla productiva disponible aunque fluctúe la facturación a corto plazo."),
    ("640000002", "fijos_operativos", "Plantilla necesaria para operar el negocio a corto plazo."),
    ("642000001", "fijos_operativos", "Coste asociado a plantilla productiva fija a corto plazo."),
    ("642000002", "fijos_operativos", "Coste recurrente asociado a la plantilla."),
    ("642000004", "fijos_operativos", "Coste asociado a plantilla indirecta fija a corto plazo."),
    ("649000001", "fijos_operativos", "Coste de personal necesario para la operativa."),
    ("649000002", "fijos_operativos", "Equipamiento de plantilla para operar."),
    ("649000004", "fijos_operativos", "Coste de soporte a la plantilla."),
    ("649000005", "fijos_operativos", "EPI necesario para la operativa."),
    ("621000001", "fijos_operativos", "Infraestructura necesaria para fabricar, independiente del volumen a corto plazo."),
    ("621000002", "fijos_operativos", "Medio operativo contratado con cuota fija."),
    ("621000007", "fijos_operativos", "Medio operativo con cuota fija."),
    ("621000010", "fijos_operativos", "Capacidad productiva contratada con coste fijo."),
    ("623000005", "fijos_operativos", "Sistemas necesarios para operar, coste recurrente."),
    ("623000006", "fijos_operativos", "Servicio recurrente necesario para operar."),
    ("623000008", "fijos_operativos", "Servicio recurrente de las instalaciones."),
    ("623000015", "fijos_operativos", "Obligación recurrente vinculada a plantilla/operativa."),
    ("625000001", "fijos_operativos", "Seguro de infraestructura operativa."),
    ("625000002", "fijos_operativos", "Seguro de medios de transporte operativos."),
    ("628000003", "fijos_operativos", "Servicio básico de instalaciones; poco sensible al volumen."),
    ("628000005", "fijos_operativos", "Servicio recurrente necesario para operar."),
    ("628000007", "fijos_operativos", "Soporte recurrente de instalaciones."),
    ("623000001", "estructura", "Retribuciones de Javier/Vicky y alquileres gestionados vía Ramos Management; estructura de dirección/holding."),
    ("623000003", "estructura", "Asesoramiento corporativo/administrativo."),
    ("623000009", "estructura", "Servicio administrativo/corporativo."),
    ("623000013", "estructura", "Gasto corporativo/administrativo."),
    ("623000023", "estructura", "Asesoramiento; clasificado como estructura salvo que se demuestre imputación directa a OF."),
    ("627000001", "estructura", "Gasto comercial/corporativo, no necesario para fabricar una unidad adicional."),
    ("627000004", "estructura", "Gasto corporativo no productivo."),
    ("627000005", "estructura", "Gasto corporativo no productivo."),
    ("628000004", "estructura", "Gasto administrativo."),
    ("628000006", "estructura", "Gasto administrativo."),
    ("628000010", "estructura", "Gasto administrativo/estructura."),
    ("631000001", "estructura", "Coste corporativo/fiscal no ligado al volumen producido."),
]


class LiraCuentaBloque(models.Model):
    _name = "lira.cuenta.bloque"
    _description = "Cuenta contable clasificada por bloque de coste"
    _order = "bloque, code"

    code = fields.Char(string="Código cuenta", required=True, index=True)
    name = fields.Char(string="Nombre cuenta", compute="_compute_account", store=True)
    bloque = fields.Selection(BLOQUES, string="Bloque", required=True, index=True)
    motivo = fields.Char(string="Criterio / motivo")
    account_id = fields.Many2one("account.account", compute="_compute_account", store=False,
                                 string="Cuenta del plan contable")
    codigo_existe = fields.Boolean(string="Código encontrado", compute="_compute_account",
                                   store=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)",
         "Esa cuenta ya está clasificada en esta empresa."),
    ]

    @api.depends("code", "company_id")
    def _compute_account(self):
        for rec in self:
            acc = self.env["account.account"].search([
                ("code", "=", rec.code),
                ("company_ids", "in", rec.company_id.id),
            ], limit=1) if rec.code else False
            rec.account_id = acc
            rec.codigo_existe = bool(acc)
            rec.name = acc.name if acc else (rec.code or "")

    @api.model
    def mapa(self):
        """{código de cuenta: bloque} con lo configurado y activo."""
        return {r.code: r.bloque for r in self.search([("active", "=", True)])}

    @api.model
    def _sembrar(self):
        """Crea las filas de la clasificación del asesor que falten."""
        existentes = set(self.search([]).mapped("code"))
        creadas = 0
        for code, bloque, motivo in SEED:
            if code in existentes:
                continue
            self.create({"code": code, "bloque": bloque, "motivo": motivo})
            creadas += 1
        return creadas

    @api.model
    def action_open(self):
        self._sembrar()
        return {
            "type": "ir.actions.act_window",
            "name": "Clasificación de costes por bloques",
            "res_model": "lira.cuenta.bloque",
            "view_mode": "list",
            "views": [[False, "list"]],
            "context": {"search_default_group_bloque": 1},
            "target": "current",
        }
