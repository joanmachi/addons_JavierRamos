/** @odoo-module */

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
export class AsistenciaDialog extends ConfirmationDialog {
    
    static template = "javier_ramos_taller.AsistenciaDialog";
    static props = {
        ...ConfirmationDialog.props,
        reload: { type: Function, optional: true },
    }

    setup() {
      this.orm = useService('orm');
      this.dialog = useService("dialog");
      this.notification = useService("notification");
    }

    async validate() {
        const args = [false, document.getElementById("aux_pin").value];
        const params = {};
        const action = await this.orm.call("hr.attendance", 'iniciar_taller_pin', args);
        console.log(action);
        console.log(typeof action);
        if (action && typeof action === "object") {
            console.log('hola');
            this.notification.add(action.msg, { type: "success", className: "fa-2x" });
            this.dialog.closeAll();
        
        }
    }
    async cancel() {
        console.log('cancel');
        console.log(this.props);
        this.dialog.closeAll();
    }
}
