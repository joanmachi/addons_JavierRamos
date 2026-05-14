/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { PickingTypeDashboardGraphField } from "@stock/picking_type_dashboard_graph/picking_type_dashboard_graph_field";
patch(PickingTypeDashboardGraphField.prototype, {
    getBarChartConfig() {
        const config = super.getBarChartConfig();
        const self = this;

        config.options.layout = { padding: { top: 30 } };
        config.plugins = [{
            id: 'stock_custom_labels',
            afterDatasetsDraw(chart) {
                const { ctx, data } = chart;
                ctx.save();
                ctx.font = 'bold 11px sans-serif';
                ctx.fillStyle = '#714B67';
                ctx.textAlign = 'center';
                const meta = chart.getDatasetMeta(0);
                console.log(self.props.record.data.kanban_dashboard_graph);
                meta.data.forEach((bar, index) => {
                    // 'count' is the bar height (the original data)
                    const count = data.datasets[0].data[index];
                    
                    // Access the custom 'total_amount' we injected in Python
                    // Odoo 18 stores the raw objects in the component's props or data
                    const rawData = self.props.record.data.kanban_dashboard_graph;
                    const parsedData = JSON.parse(rawData)[0].values[index];
                    const totalAmount = parsedData.total_amount || 0;

                    if (count > 0) {
                        const label = `${totalAmount.toLocaleString()} €`;
                        ctx.fillText(label, bar.x, bar.y - 10);
                    }
                });
                ctx.restore();
            }
        }];
        return config;
    }
});