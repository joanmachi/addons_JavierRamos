"""Al actualizar: crear el reparto de costes del taller y rellenar los cuadros.

Deja listo lo que el cliente tendría que teclear a mano: las categorías de coste
con sus cuentas contables y sus centros de trabajo (el reparto que hacía el
cuadro de mando antiguo), y todos los registros semanales/mensuales calculados
con lo que ya hay en la contabilidad, el almacén y los fichajes.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Reparto del gasto del taller. Cada categoría puede tirar de cuentas contables
# (prefijo de código) y/o de centros de trabajo valorados a un precio por hora,
# igual que en la hoja "registro P.Hora" del cuadro antiguo.
CATEGORIAS = [
    # nombre, orden, tipo, prefijos de cuenta, centros (por nombre), €/h, ICAP
    ("Herramienta de máquinas", 10, "directo", ("600000017", "600000018", "600000001"), (), 0, True),
    ("Consumibles", 20, "directo", ("600000014", "600000016", "600000019", "600000020"), (), 0, True),
    ("Electricidad", 30, "directo", ("628000001",), (), 0, False),
    ("Reparación externa", 40, "directo", ("622000002", "622000003", "622000004"),
     ("SERVICIOS EXTERNOS",), 29.0, True),
    ("Mantenimiento instalaciones", 50, "directo", ("622000001",), (), 0, True),
    ("Logística", 60, "directo", (), ("LOGISTICA",), 23.0, False),
    ("Programación CNC", 70, "directo", (), ("PROGRAMACION",), 29.0, False),
    ("Amortizaciones", 100, "gasto", ("68",), (), 0, False),
    ("Personal directo", 110, "gasto", ("640000001", "642000001"), (), 0, False),
    ("Personal indirecto", 120, "gasto", ("640000002", "642000004"), (), 0, False),
    ("Alquileres", 130, "gasto", ("621",), (), 0, False),
    ("Servicios profesionales", 140, "gasto", ("6230000", "623000001", "623000002", "623000003", "623000005", "623000006", "623000007", "623000008", "623000009"), (), 0, False),
    ("Seguros", 150, "gasto", ("625",), (), 0, False),
    ("ETT", 155, "gasto", ("623000004", "644200000"), (), 0, False),
    ("Gastos de funcionamiento", 160, "gasto",
     ("627", "628000003", "628000005", "628000007", "628000008", "628000010",
      "631", "649", "642000002"), (), 0, False),
]


def _crear_categorias(env):
    Cat = env["apunts.cmp.coste.categoria"]
    Acc = env["account.account"].with_company(env.company.id)
    WC = env["mrp.workcenter"]
    creadas = 0
    for nombre, orden, tipo, prefijos, centros, tarifa, icap in CATEGORIAS:
        if Cat.search_count([("name", "=", nombre)]):
            continue
        cuentas = []
        for p in prefijos:
            cuentas += Acc.search([("code", "=like", p + "%")]).ids
        wcs = []
        for c in centros:
            wcs += WC.search([("name", "ilike", c)]).ids
        Cat.create({
            "name": nombre, "secuencia": orden, "tipo": tipo,
            "account_ids": [(6, 0, cuentas)], "workcenter_ids": [(6, 0, wcs)],
            "tarifa_hora": tarifa, "cuenta_icap": icap,
        })
        creadas += 1
    return creadas


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = _crear_categorias(env)
        _logger.info("Cuadro de mando: %s categorías de coste creadas.", n)
    except Exception as e:
        _logger.warning("Cuadro de mando: no se pudieron crear las categorías: %s", e)
    for modelo, etiqueta in (("apunts.cmi.semana", "registro semanal (CMI)"),
                             ("apunts.cmp.mes", "producción por centro y operario"),
                             ("apunts.cmp.indicador", "índices de producción"),
                             ("apunts.cmp.coste", "precio por hora")):
        try:
            n = env[modelo].reconstruir_historico()
            _logger.info("Cuadro de mando: %s reconstruido (%s filas).", etiqueta, n)
        except Exception as e:
            _logger.warning("Cuadro de mando: no se pudo reconstruir %s: %s", etiqueta, e)
