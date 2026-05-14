import { patch } from '@web/core/utils/patch';
import { MrpRegisterProductionDialog } from '@mrp_workorder/mrp_display/dialog/mrp_register_production_dialog';
import { MrpQualityCheckConfirmationDialog } from "@mrp_workorder/mrp_display/dialog/mrp_quality_check_confirmation_dialog";
import { fetchOperationNote, MrpWorkorder } from "@mrp_workorder/mrp_display/mrp_record_line/mrp_workorder";
import { Component } from '@odoo/owl';
import { session } from '@web/session';
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

patch(MrpRegisterProductionDialog.prototype, {
    
     setup() {
        super.setup();
        this.dialog = useService("dialog");
        
    },
    async doActionAndClose(action, saveModel = true, reloadChecks = false) {
        this.state.disabled = true;
        if (saveModel) {
            var valor_input = false
            if(document.getElementById("aux_producir")){
                valor_input = document.getElementById("aux_producir").value
                if(isNaN(valor_input)){
                    valor_input = 0;
                }

            }
            this.valor_input = valor_input;
            this.current_check = false
            await this.props.record.save();
            // Calls `set_qty_producing` because the onchange won't be triggered.
            //Control de calidad
            const current_check_id = this.props.worksheetData.current_quality_check_id[0];
            let check = false;
            if (current_check_id) {
                for (const element of this.props.worksheetData.check_ids.records) {
                    console.log(element);
                    if(element.data.id == current_check_id){
                        check = element;
                        this.current_check = element;
                        break;
                    }
                }
            }
            //
            if(valor_input){
                console.log('if valor input');
                console.log(valor_input);
                if(check){
                    return this.displayInstruction(check, this.props.worksheetData);
                }else{

                    await this.props.record.model.orm.call("mrp.production", "add_cantidad", [this.props.record.resIds, valor_input, this.props.worksheetData.id ]);
                }
                
            }else{
                console.log('else valor input');
                console.log(valor_input);
                if(check){
                    return this.displayInstruction(check, this.props.worksheetData);
                }else{

                    await this.props.record.model.orm.call("mrp.production", "set_qty_producing", this.props.record.resIds);
                }

            }
        }
        await this.props.reload(this.props.record);
        this.props.close();
    },


    async displayInstruction(record, workorder) {
        console.log('displayInstruction');
        console.log(record);
        let previousQC, nextQC;
   
     

      
        if (workorder.has_operation_note && !workorder.operation_note) {
            workorder.operation_note = await fetchOperationNote(this);
        }
        const params = {
            body: record.note,
            record,
            reload: this.props.reload.bind(this),
            title: record.title,
            checkInstruction: workorder.operation_note,
            qualityCheckDone: this.qualityCheckDone.bind(this),
            cancel: () => {
            },
        };

        this.dialog.add(MrpQualityCheckConfirmationDialog, params);
    },
    async qualityCheckDone(updateChecks = false, qualityState = "pass") {
        console.log('this.valor_input');
        console.log(this.valor_input);
        await this.props.record.model.orm.call("quality.check", "update_cantidad_hecha", [this.current_check.resIds, this.valor_input]);
        if(this.valor_input){
            await this.props.record.model.orm.call("mrp.production", "add_cantidad", [this.props.record.resIds, this.valor_input, this.props.worksheetData.id ]);

        }else{
            await this.props.record.model.orm.call("mrp.production", "set_qty_producing", this.props.record.resIds);

        }
        await this.props.reload(this.props.record);
        this.props.close();
        
    }
    
});