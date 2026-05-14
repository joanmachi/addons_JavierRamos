
import { patch } from '@web/core/utils/patch';
import { Component } from "@odoo/owl";
import { MrpDisplayEmployeesPanel } from '@mrp_workorder/mrp_display/employees_panel';
import { AsistenciaDialog } from './asistencia_dialog';
import { useService } from "@web/core/utils/hooks";
patch(MrpDisplayEmployeesPanel.prototype, {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        
        
    },
    popupAsistencia() {
        const title = 'Asistencia';
        const params = {
            body: "",
            reload: this.env.reload.bind(this),
            title,
        };
        this.dialog.add(AsistenciaDialog, params);
    }

    
});