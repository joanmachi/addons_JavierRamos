/** @odoo-module **/

import { QtyInputDialog } from "@apunts_barcode_workorder/js/qty_dialog";

export class QtyInputDialogZero extends QtyInputDialog {
    confirm() {
        const raw = (this.state.qty === false || this.state.qty === "" || this.state.qty === null)
            ? 0
            : this.state.qty;
        const val = parseFloat(raw);
        if (isNaN(val) || val < 0) {
            return;
        }
        if (this.props.maxQty !== undefined && val > this.props.maxQty) {
            this.state.error = true;
            return;
        }
        this.props.onConfirm(val);
        this.props.close();
    }
}
