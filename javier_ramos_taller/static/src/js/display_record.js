import { patch } from '@web/core/utils/patch';

import { _t } from "@web/core/l10n/translation";
import { MrpDisplayRecord } from '@mrp_workorder/mrp_display/mrp_display_record';
import { MrpRegisterProductionDialog } from "@mrp_workorder/mrp_display/dialog/mrp_register_production_dialog";
import { Component } from '@odoo/owl';
import { session } from '@web/session';
import { rpc } from "@web/core/network/rpc";

patch(MrpDisplayRecord.prototype, {

    
    registerProduction() {
        const { resModel, resId } = this.props.record;
        let title = '';
        if(resModel == "mrp.workorder"){
            if (this.record.is_last_unfinished_wo){
                title = _t("Register Production: %s", this.props.production.data.product_id[1]);
            }
            else{
                title = _t("Register orden de trabajo: %s", this.props.production.data.product_id[1]);
            }
            
        }else{
            title = _t("Register Production: %s", this.props.production.data.product_id[1]);

        }
        let order_id = false
        if (resModel == "mrp.workorder") {
            order_id = this.record;
        }
        const params = {
            body: "",
            record: this.props.production,
            reload: this.env.reload.bind(this),
            title,
            qtyToProduce: this.record.qty_remaining,
            worksheetData: order_id
        };
        this.dialog.add(MrpRegisterProductionDialog, params);
    },

    async quickRegisterProduction() {
        return this.registerProduction();
       
    },

    async startWorking(shouldStop = false) {
        const { resModel, resId } = this.props.record;
        if (resModel !== "mrp.workorder") {
            return;
        }
        await this.props.updateEmployees();
        const admin_id = this.props.sessionOwner.id;
        if (
            admin_id &&
            !this.props.record.data.employee_ids.records.some((emp) => emp.resId == admin_id)
        ) {
            await this.model.orm.call(resModel, "button_start", [resId], {
                context: { mrp_display: true },
            });
            await this.env.reload(this.props.production);
           
        } else if (shouldStop) {
            await this.model.orm.call(resModel, "stop_employee", [resId, [admin_id]]);
        }
        await this.env.reload(this.props.production);
    },

    async validate() {
        const { resModel, resId } = this.props.record;
        if (resModel === "mrp.workorder") {
         
            this.validatingEmployee = this.props.sessionOwner.id;
            if (this.props.record.data.employee_ids.records.some((emp) => emp.resId == this.validatingEmployee)) {
                await this.model.orm.call(resModel, "stop_employee", [resId, [this.validatingEmployee]]);
                await this.props.record.load();
            }
            await this.props.record.save();
            const action = await this.model.orm.call(resModel, "pre_record_production", [resId]);
            if (action && typeof action === "object") {
                action.context.skip_redirection = true;
                return this._doAction(action);
            }
        }
        if (resModel === "mrp.production") {
            const args = [this.props.production.resId];
            const params = {};
            let methodName = "pre_button_mark_done";
            if (this.trackingMode === "mass_produce") {
                methodName = "action_mass_produce";
            }
            const action = await this.model.orm.call("mrp.production", methodName, args, params);
            // If there is a wizard while trying to mark as done the production, confirming the
            // wizard will straight mark the MO as done without the confirmation delay.
            if (action && typeof action === "object") {
                if (action.context.marked_as_done) {
                    this.state.validated = true;
                    this.env.reload();
                } else {
                    action.context.skip_redirection = true;
                    return this._doAction(action);
                }
            }
        }

        // Makes the validation taking a little amount of time (see o_fadeout_animation CSS class).Add commentMore actions
        this.props.addToValidationStack(this.props.record, () => this.realValidation());
        this.state.underValidation = true;
    }

    
});