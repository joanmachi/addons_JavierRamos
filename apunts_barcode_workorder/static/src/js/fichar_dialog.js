/** @odoo-module **/
import { Component, xml, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
export class FicharInputDialog extends ConfirmationDialog  {
    static template = "apunts_barcode_workorder.introducir_pin";

 
    static props = {
        ...ConfirmationDialog.props,
        barcode: { type: String },
        onConfirm: Function,
        close: Function,
    }

    setup() {
        super.setup();
        this.state = useState({ 
            barcode: false,
            error: false 
        });
    }

    confirm() {
     
        if (!this.state.barcode) {
            this.state.error = true;
            return;
        }

        this.props.onConfirm(this.state.barcode);
        this.props.close();
    }
}
