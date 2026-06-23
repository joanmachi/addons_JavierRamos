/** @odoo-module **/
import { Component, xml, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
export class QtyInputDialog extends ConfirmationDialog  {
    static template = "apunts_barcode_workorder.elegir_cantidad";

 
    static props = {
        ...ConfirmationDialog.props,
        maxQty: { type: Number },
        onConfirm: Function,
        close: Function,
    }

    setup() {
        super.setup();
        this.state = useState({ 
            qty: false,
            error: false 
        });
    }

    confirm() {
        const val = parseFloat(this.state.qty);
        // Hay que teclear un número (0 permitido: el operario puede registrar
        // que no ha producido nada en esta sesión). Vacío o negativo no vale.
        if (isNaN(val) || val < 0) {
            this.state.error = true;
            return;
        }

        // No se puede registrar más de lo pendiente: avisa y obliga a corregir.
        if (val > this.props.maxQty) {
            this.state.error = true;
            return;
        }

        this.props.onConfirm(val);
        this.props.close();
    }
}
