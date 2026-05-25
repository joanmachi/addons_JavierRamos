/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodeMRPModel from "@stock_barcode_mrp/models/barcode_mrp_model";
import { QtyInputDialogZero } from "@apunts_taller_control/js/qty_dialog_zero";

patch(BarcodeMRPModel.prototype, {
    async iniciar_parar_orden(barcode) {
        if (!barcode || !barcode.startsWith("FAB/MO")) {
            return super.iniciar_parar_orden(barcode);
        }
        if (!this.selectedEmployee) {
            return super.iniciar_parar_orden(barcode);
        }
        const wo = this.workorderLines && this.workorderLines.find(w => w.barcode === barcode);
        const empId = this.selectedEmployee.id;
        const empleadoYaFichado = wo && wo.employee_ids && wo.employee_ids.includes(empId);
        if (empleadoYaFichado) {
            return new Promise((resolve) => {
                this.dialogService.add(QtyInputDialogZero, {
                    title: `Piezas hechas en ${wo.name || "esta OT"}`,
                    body: "Pon 0 si no produjiste piezas. Queda registro en el chatter de la OF.",
                    defaultValue: 0,
                    onConfirm: async (qty) => {
                        const respuesta = await this.orm.call(
                            "mrp.production",
                            "apunts_iniciar_parar_orden_con_qty",
                            [this.resId, barcode, this.selectedEmployee, qty || 0],
                        );
                        if (respuesta && respuesta.error) {
                            this.notification(respuesta.mensaje, { type: "danger", sticky: true });
                        } else if (respuesta) {
                            this.notification(respuesta.mensaje || "Fichaje cerrado", { type: "success" });
                        }
                        await this.refrescarDatos();
                        resolve();
                    },
                });
            });
        }
        const check = await this.orm.call(
            "mrp.production",
            "apunts_chequear_sobre_fichaje",
            [this.resId, barcode, this.selectedEmployee],
        );
        if (check && check.has_open) {
            const wizardId = await this.orm.call(
                "mrp.production",
                "apunts_crear_wizard_sobre_fichaje",
                [this.resId, barcode, this.selectedEmployee],
            );
            await this.action.doAction(
                {
                    type: "ir.actions.act_window",
                    name: "Sobre-fichaje detectado",
                    res_model: "apunts.sobre.fichaje.wizard",
                    view_mode: "form",
                    res_id: wizardId,
                    views: [[false, "form"]],
                    target: "new",
                },
                {
                    onClose: async () => {
                        await this.refrescarDatos();
                    },
                },
            );
            return;
        }
        return super.iniciar_parar_orden(barcode);
    },
});
