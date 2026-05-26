import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class SupervisorListController extends ListController {
    setup() {
        super.setup();
        this._orm = useService("orm");
        this._action = useService("action");
    }

    async openRecord(record) {
        const action = await this._orm.call(
            "mrp.workorder",
            "action_open_production",
            [record.resId]
        );
        this._action.doAction(action);
    }
}

registry.category("views").add("lira_supervisor_list", {
    ...listView,
    Controller: SupervisorListController,
});
