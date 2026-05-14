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
        if (isNaN(val) || val <= 0) return;

        // Validation against Max Qty
        if (val > this.props.maxQty) {
            this.state.error = true;
            return;
        }

        this.props.onConfirm(val);
        this.props.close();
    }
}
