import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def iniciar_parar_orden(self, barcode, empleado):
        if empleado and empleado.get("id"):
            emp = self.env["hr.employee"].browse(empleado["id"])
            if emp.exists() and emp.apunts_taller_bloqueado:
                motivo = emp.apunts_taller_motivo_bloqueo or "sin motivo registrado"
                return {
                    "error": True,
                    "mensaje": "Empleado %s bloqueado en taller. Motivo: %s. Pasa por oficina." % (emp.name, motivo),
                }
            if emp.exists() and emp.attendance_state != "checked_in":
                emp.sudo()._attendance_action_change()
        return super().iniciar_parar_orden(barcode=barcode, empleado=empleado)

    def apunts_crear_wizard_sobre_fichaje(self, barcode_nueva, empleado):
        productividades = self.env["mrp.workcenter.productivity"].search([
            ("employee_id", "=", empleado["id"]),
            ("date_end", "=", False),
        ])
        otras = productividades.filtered(
            lambda p: p.workorder_id and p.workorder_id.barcode != barcode_nueva
        )
        wizard = self.env["apunts.sobre.fichaje.wizard"].create({
            "barcode_nueva": barcode_nueva,
            "employee_int_id": empleado["id"],
            "employee_name": empleado.get("name") or "",
            "res_id_int": self.id,
            "linea_ids": [(0, 0, {
                "productivity_id": p.id,
                "of_id": p.workorder_id.production_id.id,
                "ot_name": p.workorder_id.name or "?",
                "inicio": p.date_start,
            }) for p in otras],
        })
        return wizard.id

    def apunts_chequear_sobre_fichaje(self, barcode_nueva, empleado):
        if not empleado or not empleado.get("id"):
            return {"has_open": False}
        productividades = self.env["mrp.workcenter.productivity"].search([
            ("employee_id", "=", empleado["id"]),
            ("date_end", "=", False),
        ])
        otras = productividades.filtered(
            lambda p: p.workorder_id and p.workorder_id.barcode != barcode_nueva
        )
        if not otras:
            return {"has_open": False}
        p = otras[0]
        wo = p.workorder_id
        return {
            "has_open": True,
            "productivity_id": p.id,
            "of_id": wo.production_id.id,
            "of_name": wo.production_id.name or "?",
            "wo_id": wo.id,
            "ot_name": wo.name or "?",
            "inicio": str(p.date_start) if p.date_start else "",
        }

    def apunts_resolver_sobre_fichaje(self, barcode_nueva, empleado, accion):
        # Único flujo soportado: "mantener_doble" — el operario mantiene las OFs
        # anteriores abiertas y arranca también la nueva.
        return self.iniciar_parar_orden(barcode=barcode_nueva, empleado=empleado)

    def apunts_iniciar_parar_orden_con_qty(self, barcode, empleado, qty=0):
        res = self.iniciar_parar_orden(barcode=barcode, empleado=empleado)
        if not res.get("error"):
            wo = self.env["mrp.workorder"].search([("barcode", "=", barcode)], limit=1)
            if wo:
                try:
                    wo.sudo().write({
                        "qty_ready_to_validate": (wo.qty_ready_to_validate or 0.0) + (qty or 0.0),
                    })
                except Exception as e:
                    _logger.warning("Apunts: write qty_ready_to_validate falló: %s", e)
                emp_name = (empleado or {}).get("name", "?")
                wo.production_id.message_post(
                    body="Cierre fichaje — %s reportó %s piezas en %s."
                         % (emp_name, qty, wo.name)
                )
        return res
