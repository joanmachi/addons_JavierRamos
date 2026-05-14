/** @odoo-module **/

import MainComponent from "@stock_barcode/components/main";
import BarcodeMRPModel from "@stock_barcode_mrp/models/barcode_mrp_model";
import OrdenComponent from '@apunts_barcode_workorder/js/orden';
import {QtyInputDialog} from '@apunts_barcode_workorder/js/qty_dialog';
import {UpdateQtyInputDialog} from '@apunts_barcode_workorder/js/update_qty_dialog';
import {FicharInputDialog} from '@apunts_barcode_workorder/js/fichar_dialog';
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { xml, Component } from "@odoo/owl";

patch(MainComponent.prototype, {
    setup() {
        super.setup(...arguments);
        const busService = useService("bus_service");
        busService.subscribe("barcode_refresh_requested", (payload, {id: notifyID}) => {
            
            if (payload.production_id === this.env.model.resId) {
                console.log("Refreshing UI for MO:", payload.production_id);
                this.env.model.refreshFromWizard();
            }else{
                console.log('else barcode_refresh_requested ')
            }


        });


    },

    isEnableWorkorder(wo) {
        console.log('-------- isEnableWorkorder');
        console.log(wo.employee_ids);
        if(!wo){
            return false;
        }
        if (!this.env.model.empleadoElegido){
            return true;
        }
        return wo.employee_ids.includes(this.env.model.empleadoElegido.id);
      
    },
    async openQtyDialog(wo) {
        const woName = (wo && wo.name) ? wo.name : "Orden de trabajo";
        const max = wo.prev_validated_qty - wo.qty_ready_to_validate;
        this.env.services.dialog.add(QtyInputDialog, { 
            maxQty: max,
            title: woName,
            body: '',
            onConfirm: async (qty) => {
                if (!isNaN(qty)) {
                    await this.orm.call('mrp.workorder', 'write', [[wo.id], {
                    'qty_ready_to_validate': wo.qty_ready_to_validate + qty
                    }]);
                    await this.orm.call("mrp.production", "enviar_notificacion", [this.env.model.resId, qty, this.env.model.selectedEmployee, wo.name]);
                    await this.orm.call('mrp.workorder', 'finalizar_fichaje', [wo.id,this.env.model.selectedEmployee, qty]);
    
                    await this.env.model.refrescarDatos();
                }
            },

        });
    },
    async openUpdateQtyDialog(wo) {
        const woName = (wo && wo.name) ? wo.name : "Orden de trabajo";
        const max = wo.prev_validated_qty || 0;
        this.env.services.dialog.add(UpdateQtyInputDialog, { 
            maxQty: max,
            title: woName,
            body: '',
            onConfirm: async (qty) => {
                if (!isNaN(qty)) {
                    await this.orm.call('mrp.workorder', 'write', [[wo.id], {
                    'qty_ready_to_validate': qty
                    }]);
                    await this.orm.call("mrp.production", "enviar_notificacion", [this.env.model.resId, qty, this.env.model.selectedEmployee, wo.name]);
                    await this.orm.call('mrp.workorder', 'finalizar_fichaje', [wo.id,this.env.model.selectedEmployee]);
    
                    await this.env.model.refrescarDatos();
                }
            },

        });
    },
    async openFicharDialog() {

        this.env.services.dialog.add(FicharInputDialog, { 
            title: 'Introduzca su PIN',
            body: '',
            barcode: '',
            onConfirm: async (barcode) => {
                if(barcode){
                    this.env.model.iniciarFichajeEmpleado(barcode);
                }
            },

        });
    },

 

   

});

MainComponent.components.Orden = OrdenComponent;
