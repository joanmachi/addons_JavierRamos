import { patch } from '@web/core/utils/patch';

import { _t } from "@web/core/l10n/translation";
import { MrpDisplayRecord } from '@mrp_workorder/mrp_display/mrp_display_record';
import { MrpQualityCheckConfirmationDialog } from "@mrp_workorder/mrp_display/dialog/mrp_quality_check_confirmation_dialog";
import { Component } from '@odoo/owl';
import { session } from '@web/session';
import { rpc } from "@web/core/network/rpc";

patch(MrpQualityCheckConfirmationDialog.prototype, {

    
    async doActionAndClose(action, saveModel = true, reloadChecks = false){
        if (saveModel) {
            await this.props.record.save();
        }
        const res = await this.props.record.model.orm.call(this.props.record.resModel, action, [this.props.record.resId]);
        if (res) {
            this.action.doAction(res, {
                onClose: () => {
                    this.props.reload(this.props.record);
                },
            });
         
        }
        if (!reloadChecks) {
            await this.props.record.load();
        }
        await this.props.qualityCheckDone(reloadChecks, this.props.record.data.quality_state);
        this.props.close();
    }

    
});