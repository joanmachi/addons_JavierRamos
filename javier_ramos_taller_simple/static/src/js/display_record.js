import { patch } from '@web/core/utils/patch';

import { _t } from "@web/core/l10n/translation";
import { MrpDisplayRecord } from '@mrp_workorder/mrp_display/mrp_display_record';
import { MrpRegisterProductionDialog } from "@mrp_workorder/mrp_display/dialog/mrp_register_production_dialog";
import { Component } from '@odoo/owl';
import { session } from '@web/session';
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
patch(MrpDisplayRecord.prototype, {

 
    setup() {
        super.setup();
        console.log(this.props)
    },

  
    
});