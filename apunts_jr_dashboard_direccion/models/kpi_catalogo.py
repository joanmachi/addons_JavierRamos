"""Catálogo del Panel de Dirección: los 6 Indicadores de Dirección y sus KPIs.

Cada KPI sabe cómo se llama, a qué bloque pertenece, cómo se formatea, con qué
criterio se pone en verde/amarillo/rojo y a qué pantalla de detalle lleva. La
"cabecera estándar" (valor actual · objetivo · semana anterior · variación ·
misma semana del año anterior · estado) se calcula al vuelo sobre el histórico
semanal, sin duplicar datos.

La navegación que pidió la empresa: Panel (6 bloques) → KPIs del bloque →
evolución semanal → detalle de siempre.
"""

from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

ESTADOS = [("green", "Bien"), ("yellow", "Vigilar"), ("red", "Mal"), ("grey", "Sin objetivo")]
ESTADO_TXT = {"green": "Bien", "yellow": "Vigilar", "red": "Mal", "grey": "Sin objetivo"}
CSS_BORDE = {"green": "border-success", "yellow": "border-warning", "red": "border-danger"}
CSS_TEXTO = {"green": "text-success", "yellow": "text-warning", "red": "text-danger"}
CSS_BADGE = {"green": "text-bg-success", "yellow": "text-bg-warning", "red": "text-bg-danger"}

# ── Los 6 Indicadores de Dirección (mapa de la reunión semanal) ──────────────
BLOQUES = [
    (1, "ACTIVIDAD COMERCIAL", "¿Tenemos suficiente trabajo al ritmo de facturación?", "cdc",
     "Revisar la entrada de pedidos, la cartera y el ritmo de facturación.", "Pedidos / facturación"),
    (2, "RENTABILIDAD", "¿La actividad genera resultado?", "ebitda",
     "Abrir Costes para localizar dónde se absorbe el margen y después el P&G.", "P&G / cuentas"),
    (3, "COSTES", "¿Dónde se consumen los 100 € facturados?", "cov",
     "Identificar el bloque que se desvía y abrir sus cuentas.", "Clasificación / P&G"),
    (4, "TESORERÍA Y CIRCULANTE", "¿Tenemos liquidez y autonomía suficiente?", "dat",
     "Abrir cobros, pagos, vencimientos y bancos.", "Contabilidad / vencimientos"),
    (5, "PRODUCCIÓN", "¿Convertimos presencia en horas facturables y cumplimos las horas previstas?",
     "eficiencia", "Abrir las OF, los operarios y los centros de trabajo.", "OF / partes"),
    (6, "SERVICIO Y CALIDAD", "¿Cumplimos al cliente sin retrabajo?", "entregas_fecha",
     "Abrir las entregas tardías y las OF con retrabajo.", "Albaranes / OF / calidad"),
]

# ── Los KPIs ──────────────────────────────────────────────────────────────────
# clave, nombre, bloque, orden, principal, tipo, flujo, decimales, media_movil,
# fórmula, regla temporal, acción de detalle, fiable desde
K = lambda **kw: kw  # noqa: E731
KPIS = [
    # 1 · Actividad comercial
    K(clave="cdc", name="CDC · Cobertura de cartera", bloque=1, orden=1, principal=True, tipo="dias",
      formula="Cartera pendiente ÷ (facturado del año ÷ días productivos del año)",
      regla="Foto al cierre de la semana: cuántos días de facturación cubre la cartera. "
            "El Detalle reparte esa cartera por semana de entrega comprometida.",
      accion="panel:action_ver_cartera"),
    K(clave="fact_semana", name="Facturación de la semana", bloque=1, orden=2, tipo="eur", flujo=True,
      formula="Ingresos por ventas contabilizados en la semana (cuentas 70x, sin IVA; los abonos restan). La misma cifra que el P&G",
      regla="Flujo semanal; la gráfica muestra también el acumulado del año contra el objetivo.",
      accion="xmlid:apunts_jr_dashboard_direccion.apunts_action_facturacion_mensual_srv"),
    K(clave="pedidos_semana", name="Pedidos confirmados en la semana", bloque=1, orden=3, tipo="eur",
      flujo=True, formula="Importe sin IVA de los pedidos de venta confirmados en la semana",
      regla="Flujo semanal con acumulado del año.", accion="panel:action_ver_pedidos"),
    K(clave="cartera_pendiente", name="Cartera pendiente de servir", bloque=1, orden=4, tipo="eur",
      formula="Vendido y todavía no entregado (líneas de pedido confirmadas, a precio de línea)",
      regla="Foto al cierre de la semana. No se suma entre semanas. El Detalle reparte la cartera "
            "por semana de entrega comprometida: cuándo se va a entregar.",
      accion="panel:action_ver_cartera"),
    # 2 · Rentabilidad
    K(clave="ebitda", name="EBITDA sobre facturación", bloque=2, orden=1, principal=True, tipo="pct",
      formula="(Facturación + otros ingresos + variación de existencias − variables directos − "
              "semivariables − fijos operativos − estructura) ÷ Facturación × 100",
      regla="Acumulado desde el 1 de enero hasta el cierre de la semana.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    K(clave="margen_neto", name="Margen neto", bloque=2, orden=3, tipo="pct",
      formula="Resultado del ejercicio (EBITDA − amortizaciones − financieros + ingresos financieros) "
              "÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    K(clave="roe", name="ROE · rentabilidad del patrimonio", bloque=2, orden=4, tipo="pct",
      formula="Resultado del año ÷ Patrimonio neto al cierre × 100",
      regla="Acumulado del año sobre el patrimonio a la fecha de cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="roa", name="ROA · rentabilidad del activo", bloque=2, orden=5, tipo="pct",
      formula="Resultado del año ÷ Activo total al cierre × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="amortizaciones_pct", name="Amortizaciones sobre facturación", bloque=2, orden=6, tipo="pct",
      formula="Amortizaciones (68x) ÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    K(clave="financieros_pct", name="Gastos financieros sobre facturación", bloque=2, orden=7, tipo="pct",
      formula="Gastos financieros (66x) ÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    # 3 · Costes
    K(clave="cov", name="COV · Coste operativo sobre facturación", bloque=3, orden=1, principal=True,
      tipo="pct", formula="(Variables directos + Semivariables + Fijos operativos) ÷ Facturación × 100",
      regla="Acumulado del año. Al abrir el detalle se ven sus tres componentes mes a mes.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_evolucion_coste"),
    K(clave="variables_pct", name="Variables directos sobre facturación", bloque=3, orden=2, tipo="pct",
      formula="Variables directos ÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    K(clave="semivariables_pct", name="Semivariables sobre facturación", bloque=3, orden=3, tipo="pct",
      formula="Semivariables ÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    K(clave="fijos_pct", name="Fijos operativos sobre facturación", bloque=3, orden=4, tipo="pct",
      formula="Fijos operativos ÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_pnl_period"),
    K(clave="edv", name="EDV · Estructura y dirección sobre facturación", bloque=3, orden=5, tipo="pct",
      formula="Estructura / Dirección ÷ Facturación × 100", regla="Acumulado del año.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_cuenta_bloque"),
    # 4 · Tesorería y circulante
    K(clave="dat", name="DAT · Días de autonomía de tesorería", bloque=4, orden=1, principal=True,
      tipo="dias", formula="Primer día en que Tesorería + cobros previstos − pagos previstos − "
                           "pagos recurrentes (nóminas, impuestos) se queda a cero",
      regla="Foto semanal. 365 = no baja de cero en todo el año proyectado.", accion="dat"),
    K(clave="tesoreria_eur", name="Tesorería disponible", bloque=4, orden=2, tipo="eur",
      formula="Saldo de bancos y caja al cierre de la semana", regla="Foto al cierre.",
      accion="panel:action_ver_tesoreria"),
    K(clave="cobros_pendientes", name="Cobros pendientes", bloque=4, orden=3, tipo="eur",
      formula="Saldo de clientes al cierre de la semana", regla="Foto al cierre.",
      accion="panel:action_ver_cobros"),
    K(clave="liquidez", name="Liquidez general", bloque=4, orden=4, tipo="ratio",
      formula="Activo corriente ÷ Pasivo corriente", regla="Foto del balance al cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="liq_inmediata", name="Liquidez inmediata", bloque=4, orden=5, tipo="ratio",
      formula="(Activo corriente − Existencias) ÷ Pasivo corriente", regla="Foto del balance al cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="tesoreria", name="Ratio de tesorería", bloque=4, orden=6, tipo="ratio",
      formula="Bancos y caja ÷ Pasivo corriente", regla="Foto del balance al cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="solvencia", name="Solvencia", bloque=4, orden=7, tipo="ratio",
      formula="Activo total ÷ Pasivo total", regla="Foto del balance al cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="endeudamiento", name="Endeudamiento", bloque=4, orden=8, tipo="pct",
      formula="Pasivo total ÷ Activo total × 100", regla="Foto del balance al cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_dashboard"),
    K(clave="pmc", name="PMC · Periodo medio de cobro", bloque=4, orden=9, tipo="dias",
      formula="Saldo medio de clientes ÷ Facturación del año × días transcurridos",
      regla="Foto al cierre, con el saldo medio entre el 1 de enero y el cierre.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_aging"),
    K(clave="pmp", name="PMP · Periodo medio de pago", bloque=4, orden=10, tipo="dias",
      formula="Saldo medio de proveedores ÷ (compras + servicios exteriores del año) × días",
      regla="Foto al cierre. El semáforo lo compara con el PMC: bien si se paga más tarde de lo que se cobra.",
      accion="xmlid:lira_dashboard_contabilidad.action_lira_aging_supplier"),
    # 5 · Producción
    K(clave="eficiencia", name="Eficiencia productiva", bloque=5, orden=1, principal=True, tipo="pct",
      media_movil=True,
      formula="Horas previstas ÷ horas reales de las OT terminadas en la semana × 100 "
              "(solo OT con tiempo previsto)",
      regla="Solo la actividad de esa semana, con media móvil de 4 semanas.",
      accion="xmlid:apunts_jr_carga_centros.apunts_action_rendimiento_centro_srv"),
    K(clave="desviacion_of", name="Desviación de horas de OF", bloque=5, orden=2, tipo="pct",
      media_movil=True, formula="(Horas previstas − horas reales) ÷ horas previstas × 100. "
                                 "Positivo = ahorro; negativo = exceso",
      regla="Solo la actividad de esa semana, con media móvil de 4 semanas.",
      accion="xmlid:apunts_jr_carga_centros.apunts_action_rendimiento_operario_srv"),
    K(clave="macpre", name="MACPRE · Aprovechamiento de la presencia", bloque=5, orden=3, tipo="pct",
      media_movil=True, fiable_desde=date(2026, 6, 22),
      formula="Horas en OF de toda la plantilla (sin contar dos veces las máquinas en "
              "paralelo) ÷ horas de presencia fichadas de toda la plantilla × 100",
      regla="Solo esa semana. Toda la plantilla, oficina incluida. Fiable desde que se ficha "
            "la presencia entera (semana 26 de 2026).",
      accion="panel:action_ver_horas"),
    K(clave="macop", name="MACOP · Máquinas por operario", bloque=5, orden=4, tipo="ratio",
      media_movil=True,
      formula="Horas máquina ÷ horas en OF de los operarios de planta (el índice de siempre: "
              "cuántas máquinas lleva cada persona a la vez)",
      regla="Solo esa semana, con media móvil de 4 semanas. Solo los empleados marcados como "
            "«Operario de planta» en su ficha.",
      accion="xmlid:apunts_jr_dashboard_direccion.apunts_action_cmp_indicadores"),
    K(clave="wip_valor", name="Fabricación en curso", bloque=5, orden=5, tipo="eur",
      formula="Coste acumulado de las OF abiertas", regla="Foto al cierre.",
      accion="panel:action_ver_wip"),
    # 6 · Servicio y calidad
    K(clave="entregas_fecha", name="Entregas en fecha", bloque=6, orden=1, principal=True, tipo="pct",
      media_movil=True,
      formula="Albaranes de salida validados en o antes de la fecha comprometida ÷ total de "
              "albaranes de la semana × 100 (solo pedidos con fecha comprometida)",
      regla="Solo esa semana, con media móvil de 4 semanas.", accion="panel:action_ver_entregas"),
    K(clave="tcp", name="TCP · Tiempo de ciclo productivo", bloque=6, orden=2, tipo="dias",
      media_movil=True, formula="Media de días entre la confirmación del pedido y la entrega, "
                                 "de los albaranes validados en la semana",
      regla="Solo esa semana, con media móvil de 4 semanas.",
      accion="xmlid:stock.action_picking_tree_all"),
    K(clave="retrabajo", name="Horas de retrabajo", bloque=6, orden=3, tipo="pct", media_movil=True,
      formula="Horas fichadas en fases de retrabajo (rectificaciones del supervisor) ÷ horas "
              "totales en OF × 100",
      regla="Solo esa semana. Saldrá 0 % mientras las rectificaciones no se registren como retrabajo.",
      accion="xmlid:lira_mfg_supervisor.action_lira_refabricacion"),
]

# ── Criterios de aceptación (los del informe de la empresa) ──────────────────
# clave, nombre, verde, amarillo, sentido, relativo_a, notas
CRITERIOS = [
    ("liquidez", "Liquidez general", 1.5, 1.2, "mayor", None, "Informe JR: rojo <1,20 · amarillo 1,20–1,50 · verde ≥1,50"),
    ("liq_inmediata", "Liquidez inmediata", 1.0, 0.8, "mayor", None, "Informe JR: rojo <0,80 · amarillo 0,80–1,00 · verde >1,00"),
    ("tesoreria", "Ratio de tesorería", 0.30, 0.15, "mayor", None, "Informe JR: rojo <0,15 · amarillo 0,15–0,30 · verde >0,30"),
    ("solvencia", "Solvencia", 2.0, 1.5, "mayor", None, "Informe JR: rojo <1,50 · amarillo 1,50–2,00 · verde >2,00"),
    ("endeudamiento", "Endeudamiento (%)", 50.0, 60.0, "menor", None, "Informe JR: verde <50 · amarillo 50–60 · rojo >60"),
    ("ebitda", "EBITDA (%)", 8.0, 5.0, "mayor", None, "Informe JR: rojo <5 · amarillo 5–8 · verde >8"),
    ("margen_neto", "Margen neto (%)", 5.0, 2.0, "mayor", None, "Informe JR: rojo <2 · amarillo 2–5 · verde >5"),
    ("roe", "ROE (%)", 12.0, 7.0, "mayor", None, "Informe JR: rojo <7 · amarillo 7–12 · verde >12"),
    ("roa", "ROA (%)", 6.0, 3.0, "mayor", None, "Informe JR: rojo <3 · amarillo 3–6 · verde >6"),
    ("variables_pct", "Variables directos / facturación (%)", 40.0, 45.0, "menor", None, "Informe JR: verde <40 · amarillo 40–45 · rojo >45"),
    ("semivariables_pct", "Semivariables / facturación (%)", 12.0, 15.0, "menor", None, "Informe JR: verde <12 · amarillo 12–15 · rojo >15"),
    ("fijos_pct", "Fijos operativos / facturación (%)", 40.0, 45.0, "menor", None, "Informe JR: verde <40 · amarillo 40–45 · rojo >45"),
    ("cov", "COV — Coste operativo s/ facturación (%)", 80.0, 90.0, "menor", None, "Informe JR: verde ≤80 · amarillo 80–90 · rojo >90"),
    ("edv", "EDV — Estructura s/ facturación (%)", 8.0, 12.5, "menor", None, "Informe JR: verde ≤8 · amarillo 8–12,5 · rojo >12,5"),
    ("amortizaciones_pct", "Amortizaciones / facturación (%)", 8.0, 10.0, "menor", None, "Informe JR: verde <8 · amarillo 8–10 · rojo >10"),
    ("financieros_pct", "Gastos financieros / facturación (%)", 2.0, 3.0, "menor", None, "Informe JR: verde <2 · amarillo 2–3 · rojo >3"),
    ("pmc", "PMC (días)", 60.0, 75.0, "menor", None, "Informe JR: verde <60 · amarillo 60–75 · rojo >75"),
    ("pmp", "PMP (días) respecto al PMC", 5.0, -5.0, "mayor", "pmc", "Informe JR: verde si PMP > PMC, amarillo ≈ PMC (±5 días), rojo si PMP < PMC"),
    ("cdc", "CDC — Cobertura de cartera (días)", 60.0, 40.0, "mayor", None, "Informe JR: rojo <40 · amarillo 40–60 · verde >60"),
    ("dat", "DAT — Autonomía de tesorería (días)", 90.0, 60.0, "mayor", None, "Informe JR: rojo <60 · amarillo 60–90 · verde >90"),
    ("entregas_fecha", "Entregas en fecha (%)", 95.0, 90.0, "mayor", None, "Informe JR: rojo <90 · amarillo 90–95 · verde >95"),
    ("eficiencia", "Eficiencia productiva (%)", 99.0, 85.0, "mayor", None, "Informe JR: rojo <85 · amarillo 85–99 · verde >99"),
    ("desviacion_of", "Desviación horas OF (%)", 0.0, -15.0, "mayor", None, "Informe JR: verde ≥0 · amarillo −15–0 · rojo <−15 (positivo = ahorro)"),
    ("macpre", "MACPRE (%)", 95.0, 85.0, "mayor", None, "Informe JR: rojo <85 · amarillo 85–95 · verde ≥95"),
    ("macop", "MACOP (máquinas por operario)", 1.25, 1.0, "mayor", None, "Cuadro de siempre: objetivo 1,25"),
    ("tcp", "TCP (días)", 20.0, 30.0, "menor", None, "Informe JR: verde <20 · amarillo 20–30 · rojo >30"),
    ("retrabajo", "Horas de retrabajo (%)", 1.0, 3.0, "menor", None, "Informe JR: verde <1 · amarillo 1–3 · rojo >3"),
    ("fact_semana", "Facturación de la semana (€)", 40000.0, 30000.0, "mayor", None, "Cuadro de siempre: 40.000 €/semana (2 M€/año)"),
    ("pedidos_semana", "Pedidos de la semana (€)", 40000.0, 30000.0, "mayor", None, "Mismo ritmo que la facturación objetivo"),
    ("cartera_pendiente", "Cartera pendiente (€)", 400000.0, 300000.0, "mayor", None, "Cuadro de siempre: mínimo 400.000 €"),
    ("tesoreria_eur", "Tesorería disponible (€)", 130000.0, 100000.0, "mayor", None, "Cuadro de siempre: mínimo 130.000 € en bancos"),
]


def _fmt_num(valor, decimales):
    txt = "{:,.{d}f}".format(valor, d=decimales)
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


class ApuntsKpiBloque(models.Model):
    _name = "apunts.kpi.bloque"
    _description = "Indicador de Dirección (bloque del panel)"
    _order = "orden"

    orden = fields.Integer(string="Orden", required=True)
    name = fields.Char(string="Indicador", required=True)
    pregunta = fields.Char(string="Pregunta que responde")
    que_hacer = fields.Char(string="Qué hacer si está mal")
    nivel_detalle = fields.Char(string="Nivel de detalle")
    kpi_principal_id = fields.Many2one("apunts.kpi", string="KPI principal")
    kpi_ids = fields.One2many("apunts.kpi", "bloque_id", string="KPIs")

    principal_nombre = fields.Char(compute="_compute_resumen")
    principal_valor_txt = fields.Char(compute="_compute_resumen")
    principal_objetivo_txt = fields.Char(compute="_compute_resumen")
    principal_variacion_txt = fields.Char(compute="_compute_resumen")
    principal_anterior_txt = fields.Char(compute="_compute_resumen")
    principal_etiqueta_anterior = fields.Char(compute="_compute_resumen")
    principal_ano_anterior_txt = fields.Char(compute="_compute_resumen")
    principal_estado = fields.Selection(ESTADOS, compute="_compute_resumen")
    principal_estado_txt = fields.Char(compute="_compute_resumen")
    semana_txt = fields.Char(compute="_compute_resumen")
    n_kpis = fields.Integer(compute="_compute_resumen")
    n_rojos = fields.Integer(compute="_compute_resumen")
    n_amarillos = fields.Integer(compute="_compute_resumen")
    css_borde = fields.Char(compute="_compute_resumen")
    css_texto = fields.Char(compute="_compute_resumen")

    @api.depends_context("uid", "apunts_semana", "apunts_rango")
    def _compute_resumen(self):
        for b in self:
            p = b.kpi_principal_id
            b.principal_nombre = p.name or ""
            b.principal_valor_txt = p.valor_actual_txt if p else "—"
            b.principal_objetivo_txt = p.objetivo_txt if p else "—"
            b.principal_variacion_txt = p.variacion_txt if p else ""
            b.principal_anterior_txt = p.anterior_txt if p else ""
            b.principal_etiqueta_anterior = p.etiqueta_anterior if p else "Semana anterior"
            # En la tarjeta cabe poco: "sin dato (empieza en 2027)" se acorta
            ano_ant = p.ano_anterior_txt if p else ""
            b.principal_ano_anterior_txt = "sin dato" if ano_ant.startswith("sin dato") else ano_ant
            b.principal_estado = p.estado if p else "grey"
            b.principal_estado_txt = p.estado_txt if p else ""
            b.semana_txt = p.semana_txt if p else ""
            activos = b.kpi_ids.filtered("activo")
            b.n_kpis = len(activos)
            b.n_rojos = len(activos.filtered(lambda k: k.estado == "red"))
            b.n_amarillos = len(activos.filtered(lambda k: k.estado == "yellow"))
            b.css_borde = CSS_BORDE.get(b.principal_estado, "border-secondary")
            b.css_texto = CSS_TEXTO.get(b.principal_estado, "text-secondary")

    def action_ver_kpis(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "%d · %s" % (self.orden, self.name),
            "res_model": "apunts.kpi",
            "view_mode": "kanban,list",
            "domain": [("bloque_id", "=", self.id), ("activo", "=", True)],
            # Si se está consultando otra semana, los KPIs del bloque también
            "context": {"create": False, "delete": False,
                        "apunts_semana": self.env.context.get("apunts_semana") or False,
                        "apunts_rango": self.env.context.get("apunts_rango") or False},
            "target": "current",
        }

    def action_evolucion_principal(self):
        self.ensure_one()
        if not self.kpi_principal_id:
            raise UserError("Este indicador no tiene KPI principal configurado.")
        return self.kpi_principal_id.action_evolucion()

    @api.model
    def _sembrar(self):
        """Crea los bloques y los KPIs que falten (no pisa lo editado)."""
        Kpi = self.env["apunts.kpi"]
        bloques = {}
        for orden, name, pregunta, principal, que_hacer, nivel in BLOQUES:
            b = self.search([("orden", "=", orden)], limit=1)
            vals = {"orden": orden, "name": name, "pregunta": pregunta,
                    "que_hacer": que_hacer, "nivel_detalle": nivel}
            if b:
                b.write(vals)
            else:
                b = self.create(vals)
            bloques[orden] = (b, principal)
        for d in KPIS:
            k = Kpi.search([("clave", "=", d["clave"])], limit=1)
            vals = {
                "clave": d["clave"], "name": d["name"], "bloque_id": bloques[d["bloque"]][0].id,
                "orden": d.get("orden", 10), "principal": d.get("principal", False),
                "tipo": d.get("tipo", "pct"), "flujo": d.get("flujo", False),
                "media_movil": d.get("media_movil", False), "formula": d.get("formula", ""),
                "regla": d.get("regla", ""), "accion": d.get("accion", ""),
                "fiable_desde": d.get("fiable_desde", False),
            }
            if k:
                k.write(vals)
            else:
                Kpi.create(vals)
        for orden, (b, principal) in bloques.items():
            k = Kpi.search([("clave", "=", principal)], limit=1)
            if k:
                b.kpi_principal_id = k.id
        self._sembrar_criterios()
        return len(KPIS)

    @api.model
    def _sembrar_criterios(self):
        """Carga los criterios del informe. Los que la empresa ya haya editado
        no se tocan; solo se crean los que faltan y se actualizan los que aún
        tenían el valor genérico inicial."""
        C = self.env["lira.ratio.criterio"].sudo()
        n = 0
        for i, (clave, name, verde, amarillo, sentido, relativo, notas) in enumerate(CRITERIOS):
            rec = C.search([("clave", "=", clave)], limit=1)
            vals = {"clave": clave, "name": name, "verde": verde, "amarillo": amarillo,
                    "sentido": sentido, "relativo_a": relativo or False, "notas": notas,
                    "secuencia": (i + 1) * 10}
            if not rec:
                C.create(vals)
                n += 1
            elif (rec.notas or "").startswith("Criterio genérico inicial"):
                rec.write(vals)
                n += 1
        return n


class ApuntsKpi(models.Model):
    _name = "apunts.kpi"
    _description = "KPI de Dirección"
    _order = "bloque_id, principal desc, orden"

    clave = fields.Char(string="Clave", required=True, index=True)
    name = fields.Char(string="KPI", required=True)
    bloque_id = fields.Many2one("apunts.kpi.bloque", string="Indicador", required=True,
                                ondelete="cascade")
    orden = fields.Integer(string="Orden", default=10)
    principal = fields.Boolean(string="KPI principal del bloque")
    tipo = fields.Selection([("eur", "Euros"), ("pct", "Porcentaje"), ("dias", "Días"),
                             ("ratio", "Ratio")], string="Tipo", required=True, default="pct")
    flujo = fields.Boolean(string="Es un flujo",
                           help="Euros generados en la semana (se pueden acumular). Si no, es un saldo.")
    media_movil = fields.Boolean(string="Con media móvil de 4 semanas")
    formula = fields.Char(string="Fórmula")
    regla = fields.Char(string="Regla temporal")
    accion = fields.Char(string="Detalle (acción)",
                         help="panel:<método del Panel Dirección> · xmlid:<acción> · dat")
    fiable_desde = fields.Date(string="Fiable desde",
                               help="Antes de esta fecha el dato no es de fiar y no se guarda.")
    activo = fields.Boolean(string="Activo", default=True)

    # Cabecera estándar
    valor_actual = fields.Float(compute="_compute_cabecera", digits=(16, 4))
    valor_actual_txt = fields.Char(compute="_compute_cabecera", string="Valor actual")
    semana_txt = fields.Char(compute="_compute_cabecera", string="Semana del dato")
    objetivo_txt = fields.Char(compute="_compute_cabecera", string="Objetivo")
    anterior_txt = fields.Char(compute="_compute_cabecera", string="Semana anterior")
    etiqueta_anterior = fields.Char(compute="_compute_cabecera",
                                    help="«Semana anterior» o, consultando un periodo, «Periodo anterior (S25→S30)».")
    variacion_txt = fields.Char(compute="_compute_cabecera", string="Variación")
    ano_anterior_txt = fields.Char(compute="_compute_cabecera", string="Misma semana año anterior")
    estado = fields.Selection(ESTADOS, compute="_compute_cabecera", string="Estado")
    estado_txt = fields.Char(compute="_compute_cabecera")
    fecha_dato = fields.Date(compute="_compute_cabecera")
    css_borde = fields.Char(compute="_compute_cabecera")
    css_badge = fields.Char(compute="_compute_cabecera")

    _sql_constraints = [("clave_uniq", "unique(clave)", "Ya existe un KPI con esa clave.")]

    # ── Formato ──────────────────────────────────────────────────────────────

    def _fmt(self, valor):
        self.ensure_one()
        if valor is None:
            return "—"
        if self.tipo == "eur":
            return "%s €" % _fmt_num(valor, 0)
        if self.tipo == "pct":
            return "%s %%" % _fmt_num(valor, 1)
        if self.tipo == "dias":
            return "%s días" % _fmt_num(valor, 1)
        return _fmt_num(valor, 2)

    def _fmt_variacion(self, actual, anterior):
        self.ensure_one()
        if actual is None or anterior is None:
            return "—"
        if self.tipo == "pct":
            d = actual - anterior
            return "%s%s p.p." % ("+" if d >= 0 else "", _fmt_num(d, 1))
        if not anterior:
            return "—"
        d = (actual - anterior) / abs(anterior) * 100.0
        return "%s%s %%" % ("+" if d >= 0 else "", _fmt_num(d, 1))

    # KPIs que miden lo que pasó ESA semana (ratio semanal): en un periodo se
    # hace la media de las semanas con dato. Los flujos (facturación, pedidos)
    # se suman. Todo lo demás es acumulado del año o foto: vale el cierre.
    MEDIA_SEMANAL = ("eficiencia", "desviacion_of", "macpre", "macop", "tcp",
                     "retrabajo", "entregas_fecha")

    def _agregacion(self):
        self.ensure_one()
        if self.flujo:
            return "suma"
        if self.clave in self.MEDIA_SEMANAL:
            return "media"
        return "ultimo"

    def _valor_periodo(self, lunes_ini, lunes_fin):
        """(valor agregado, nº semanas con dato, primera fila, última fila) del
        KPI entre esos dos lunes, según su tipo de agregación."""
        Semana = self.env["apunts.kpi.semana"].sudo()
        filas = Semana.search([("clave", "=", self.clave), ("fecha", ">=", lunes_ini),
                               ("fecha", "<=", lunes_fin)], order="fecha")
        if not filas:
            return None, 0, Semana, Semana
        agg = self._agregacion()
        if agg == "suma":
            valor = sum(filas.mapped("valor"))
        elif agg == "media":
            valor = sum(filas.mapped("valor")) / len(filas)
        else:
            valor = filas[-1].valor
        return valor, len(filas), filas[0], filas[-1]

    def _cabecera_periodo(self, lunes_ini, lunes_fin, Criterio):
        """Cabecera de la tarjeta cuando se consulta un PERIODO de varias
        semanas (Elegir fechas): el acumulado del periodo, comparado con el
        periodo anterior de la misma duración."""
        n_sem = (lunes_fin - lunes_ini).days // 7 + 1
        ant_fin = lunes_ini - timedelta(days=7)
        ant_ini = ant_fin - timedelta(days=7 * (n_sem - 1))
        iso_i, iso_f = lunes_ini.isocalendar(), lunes_fin.isocalendar()
        rango_txt = "S%02d→S%02d/%s" % (iso_i[1], iso_f[1], iso_f[0])
        for k in self:
            valor, n, primera, ultima = k._valor_periodo(lunes_ini, lunes_fin)
            v_ant, n_ant, _p, _u = k._valor_periodo(ant_ini, ant_fin)
            agg = k._agregacion()
            verde, _amarillo, sentido = Criterio.criterio(k.clave)
            rel = Criterio.search([("clave", "=", k.clave)], limit=1).relativo_a
            otros = {}
            if rel:
                base = self.search([("clave", "=", rel)], limit=1)
                otros[rel] = base._valor_periodo(lunes_ini, lunes_fin)[0] if base else None
            k.valor_actual = valor or 0.0
            k.valor_actual_txt = k._fmt(valor) if valor is not None else "—"
            k.fecha_dato = ultima.fecha if ultima else False
            if valor is None:
                k.semana_txt = "%s · sin dato en el periodo" % rango_txt
            elif agg == "suma":
                k.semana_txt = "%s · suma de %d semanas" % (rango_txt, n)
            elif agg == "media":
                k.semana_txt = "%s · media de %d semanas con dato" % (rango_txt, n)
            else:
                k.semana_txt = "%s · a cierre de la S%02d" % (rango_txt, ultima.semana)
            if verde is None:
                k.objetivo_txt = "sin objetivo"
            elif rel:
                k.objetivo_txt = "%s que %s" % ("mayor" if sentido == "mayor" else "menor", rel.upper())
            else:
                k.objetivo_txt = "%s %s" % ("≥" if sentido == "mayor" else "≤", k._fmt(verde))
            k.etiqueta_anterior = "Periodo anterior (S%02d→S%02d)" % (
                ant_ini.isocalendar()[1], ant_fin.isocalendar()[1])
            k.anterior_txt = k._fmt(v_ant) if v_ant is not None else "sin dato"
            k.variacion_txt = k._fmt_variacion(valor, v_ant)
            k.ano_anterior_txt = "sin dato (empieza en 2027)"
            k.estado = Criterio.evaluar(k.clave, valor, otros) if valor is not None else "grey"
            k.estado_txt = ESTADO_TXT.get(k.estado, "") if valor is not None else "Sin dato"
            k.css_borde = CSS_BORDE.get(k.estado, "border-secondary")
            k.css_badge = CSS_BADGE.get(k.estado, "text-bg-secondary")

    @api.depends_context("uid", "apunts_semana", "apunts_rango")
    def _compute_cabecera(self):
        rango = self.env.context.get("apunts_rango")
        if rango:
            self._cabecera_periodo(fields.Date.to_date(rango[0]), fields.Date.to_date(rango[1]),
                                   self.env["lira.ratio.criterio"].sudo())
            return
        Semana = self.env["apunts.kpi.semana"].sudo()
        Criterio = self.env["lira.ratio.criterio"].sudo()
        # Con «apunts_semana» en el contexto (Consultar otra semana) la cabecera
        # enseña esa semana en vez de la última: el panel de la reunión tal y
        # como quedó guardado entonces.
        semana_ctx = self.env.context.get("apunts_semana")
        lunes_ctx = False
        if semana_ctx:
            d = fields.Date.to_date(semana_ctx)
            lunes_ctx = d - timedelta(days=d.weekday())
        for k in self:
            if lunes_ctx:
                actual = Semana.search([("clave", "=", k.clave), ("fecha", "=", lunes_ctx)], limit=1)
            else:
                actual = Semana.search([("clave", "=", k.clave)], order="fecha desc", limit=1)
            anterior = ano_ant = Semana
            if actual:
                anterior = Semana.search([("clave", "=", k.clave),
                                          ("fecha", "<", actual.fecha)], order="fecha desc", limit=1)
                ano_ant = Semana.search([("clave", "=", k.clave), ("anio", "=", actual.anio - 1),
                                         ("semana", "=", actual.semana)], limit=1)
            verde, _amarillo, sentido = Criterio.criterio(k.clave)
            rel = Criterio.search([("clave", "=", k.clave)], limit=1).relativo_a
            k.valor_actual = actual.valor if actual else 0.0
            k.valor_actual_txt = k._fmt(actual.valor) if actual else "—"
            k.fecha_dato = actual.fecha if actual else False
            if actual:
                k.semana_txt = "S%02d/%s · %s" % (
                    actual.semana, actual.anio,
                    "cerrada" if actual.cerrada else "en curso (dato de hoy)")
            elif lunes_ctx:
                iso = lunes_ctx.isocalendar()
                hay_antes = bool(Semana.search([("clave", "=", k.clave), ("fecha", "<", lunes_ctx)], limit=1))
                k.semana_txt = "S%02d/%s · %s" % (
                    iso[1], iso[0],
                    "sin actividad esa semana" if hay_antes else "aún no se registraba")
            else:
                k.semana_txt = "sin datos todavía"
            if verde is None:
                k.objetivo_txt = "sin objetivo"
            elif rel:
                k.objetivo_txt = "%s que %s" % ("mayor" if sentido == "mayor" else "menor", rel.upper())
            else:
                k.objetivo_txt = "%s %s" % ("≥" if sentido == "mayor" else "≤", k._fmt(verde))
            # Sin semana anterior no es un fallo: es la primera semana con dato
            # (p. ej. el DAT, que es una foto y no se reconstruye hacia atrás)
            k.etiqueta_anterior = "Semana anterior"
            k.anterior_txt = k._fmt(anterior.valor) if anterior else (
                "sin dato (1ª semana)" if actual else "—")
            k.variacion_txt = k._fmt_variacion(actual.valor if actual else None,
                                               anterior.valor if anterior else None)
            k.ano_anterior_txt = k._fmt(ano_ant.valor) if ano_ant else "sin dato (empieza en 2027)"
            k.estado = actual.estado if actual else "grey"
            k.estado_txt = ESTADO_TXT.get(k.estado, "") if actual else "Sin dato"
            k.css_borde = CSS_BORDE.get(k.estado, "border-secondary")
            k.css_badge = CSS_BADGE.get(k.estado, "text-bg-secondary")

    # ── Navegación ───────────────────────────────────────────────────────────

    def action_evolucion(self):
        self.ensure_one()
        graph = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_serie_graph")
        lista = self.env.ref("apunts_jr_dashboard_direccion.apunts_kpi_serie_list")
        return {
            "type": "ir.actions.act_window",
            "name": "%s · evolución semanal" % self.name,
            "res_model": "apunts.kpi.serie",
            "view_mode": "graph,list",
            "views": [(graph.id, "graph"), (lista.id, "list")],
            "domain": [("clave", "=", self.clave)],
            "context": {"search_default_ult12": 1, "fill_temporal": False,
                        "create": False, "delete": False, "edit": False},
            "target": "current",
        }

    def action_historico(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "%s · histórico" % self.name,
            "res_model": "apunts.kpi.semana",
            "view_mode": "list,pivot",
            "domain": [("clave", "=", self.clave)],
            "context": {"create": False, "delete": False},
            "target": "current",
        }

    def action_detalle(self):
        """Abre el detalle de siempre de este KPI (la pantalla donde se
        analiza el dato en profundidad)."""
        self.ensure_one()
        accion = self.accion or ""
        if accion.startswith("panel:"):
            panel = self.env["apunts.direccion.resumen"].sudo().create({})
            metodo = getattr(panel, accion[6:], None)
            if metodo:
                return metodo()
        elif accion.startswith("xmlid:"):
            rec = self.env.ref(accion[6:], raise_if_not_found=False)
            if rec:
                if rec._name == "ir.actions.server":
                    return rec.sudo().run()
                return rec.sudo().read()[0]
        elif accion == "dat":
            return self.env["apunts.dat.pago"].action_proyeccion()
        return self.action_evolucion()
