/** @odoo-module **/

import BarcodeMRPModel from "@stock_barcode_mrp/models/barcode_mrp_model";

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

patch(BarcodeMRPModel.prototype, {
    

   

    setData(data) {

        super.setData(...arguments);
        console.log("BARCODE DATA:", data);

        if (data.workcenter_id) {
            this.workorders = data.workorder_ids.filter(wo => wo.workcenter_id === data.workcenter_id);
        } else {
            this.workorders = data.workorder_ids || [];
        }
        if (this.isEnlarged === undefined) {
            this.isEnlarged = false;
        }

        // No persistimos el empleado entre sesiones: cada vez que se entra a la vista
        // empieza sin nadie fichado y el operario debe escanear su código
        if (this.selectedEmployee === undefined) {
            this.selectedEmployee = null;
        }

        this.lastToggle = 0;
        this.workorders = data.data.workorders || [];
        this.product_image = data.data.product_image;
        this.log_note = data.data.log_note;
        this.qty_produced = data.data.qty_produced ?? 0;
        this.product_qty = data.data.product_qty ?? 0;
        this.product_uom_name = data.data.product_uom_name || '';
        if (this.showComponentes === undefined) this.showComponentes = false;
        if (this.componentes === undefined) this.componentes = [];
        this.trigger('update');
    },

    toggleImage(ev) {
        console.log('toggleImage');
        const now = Date.now();
        if (now - this.lastToggle < 300) {
            return;
        }
        this.lastToggle = now;
        if (ev) { ev.stopPropagation(); }
        if (ev && ev.stopPropagation) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.isEnlarged = !this.isEnlarged;
        // This is the essential signal to refresh the UI
        this.trigger('update');
    },

    

    async refreshFromWizard() {
        
        this.refrescarDatos();
    },

    get workorderLines() {
        return this.workorders;
    },
    get empleadoElegido() {
        return this.selectedEmployee;
    },

    async comprobarDisponibilidad(){
        const respuesta = await this.orm.call(
                    'mrp.production',
                    'comprobar_disponibilidad',
                    [this.resId]
                );
        if (respuesta.error){
            this.notification(respuesta.mensaje, { type: "danger" });
            
        }else{
            this.notification(respuesta.mensaje, { type: "info" });

        }
        this.trigger('update'); 
    },

    async _processBarcode(barcode) {
        if(this.resModel != 'mrp.production'){
            return super._processBarcode(barcode);
        }
        console.log(barcode);

   
        //const employee = await this.orm.searchRead('hr.employee', [['barcode', '=', barcode]], ['id', 'name']);
        if(await this.iniciarFichajeEmpleado(barcode)){
            return;
        }
        
        //si empieza por WO
        await this.iniciar_parar_orden(barcode)
        
        
        
    },
    async iniciarFichajeEmpleado(barcode){
        const employee = await this.orm.call("hr.employee", "buscar_empleado", [false, barcode]);
        
        if (employee.length > 0) {
            this.selectedEmployee = employee[0];
            this.notification(`Fichado como ${this.selectedEmployee.name}`, { type: "info" });
            
            this.trigger('update'); 
            return true;
        }

    },
    async iniciar_parar_orden(barcode){
        if(barcode && (barcode.startsWith('FAB/MO'))){
            if (!this.selectedEmployee) {
                this.notification("Primero escanee su código de empleado", { type: 'danger' });
                return;
            }
            let respuesta = await this.orm.call(
                    'mrp.production',
                    'iniciar_parar_orden',
                    [this.resId, barcode, this.selectedEmployee]
                );
            if(respuesta.error){
    
                this.notification(respuesta.mensaje, { type: "danger" });
            }else{
                this.notification(respuesta.mensaje, { type: "info" });
            }
            this.refrescarDatos();
        }
    },

   async openQtyDialog(woId) {

    
        if (!this.selectedEmployee) {
            this.notification("Primero escanee su código de empleado", { type: 'danger' });
            return;
        }
        const wo = this.workorderLines.find(w => w.id === woId);
        if (!wo || wo.prev_validated_qty <= 0) {
            this.notification(
                "Blocked: Previous work order has not validated any units yet.", 
                { type: 'danger' }
            );
            return;
        }

        // Suggest the maximum allowed quantity as the default value
        const defaultValue = wo.prev_validated_qty || 0;
        const val = window.prompt(
            `Introduzca cantidad (Maxima: ${defaultValue}):`, 
            defaultValue
        );
        
        if (val !== null && !isNaN(val)) {
            const qty = parseFloat(val);
            
            // Validation Check
            if (qty > wo.prev_validated_qty) {
                this.notification(
                    `Cantidad maxima (${wo.prev_validated_qty})`, 
                    { type: 'danger' }
                );
                return;
            }

            // Write to custom field
            await this.orm.call('mrp.workorder', 'write', [[woId], {
                'qty_ready_to_validate': qty
            }]);
            console.log('---------')
            console.log(this.selectedEmployee)
            await this.orm.call("mrp.production", "enviar_notificacion", [this.resId, qty, this.selectedEmployee, wo.name]);

            this.refrescarDatos();
            
    }
},
async refrescarDatos(){
    const { route, params } = this.getActionRefresh(this.resId);
    const result = await rpc(route, params);
    this.setData(result);
    this.trigger('update');
},

async toggleComponentes() {
    if (this.showComponentes) {
        this.showComponentes = false;
    } else {
        this.componentes = await this.orm.call('mrp.production', 'get_componentes_barcode', [this.resId]);
        this.showComponentes = true;
    }
    this.trigger('update');
}


});

