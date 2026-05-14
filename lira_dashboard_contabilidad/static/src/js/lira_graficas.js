/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Singleton para no re-importar ni re-registrar Chart.js en cada widget
let _ChartClass = null;
let _loadPromise = null;

function loadChart() {
    if (_ChartClass) return Promise.resolve(_ChartClass);
    if (_loadPromise) return _loadPromise;
    _loadPromise = import("chart.js")
        .then(({ Chart, registerables }) => {
            try { Chart.register(...registerables); } catch (_) {}
            _ChartClass = Chart;
            return Chart;
        })
        .catch((err) => {
            console.error("[LiraCharts] Error cargando Chart.js:", err);
            _loadPromise = null;
            return null;
        });
    return _loadPromise;
}

class LiraChartField extends Component {
    static template = xml`
        <div class="lira-chart-wrapper">
            <div class="lira-chart-canvas-container">
                <canvas t-ref="canvas"/>
            </div>
            <div class="lira-chart-footer">
                <button class="lira-print-btn" t-on-click="printChart">
                    <i class="fa fa-file-pdf-o"/> Descargar PDF
                </button>
            </div>
        </div>
    `;

    static props = {
        id: { type: String, optional: true },
        name: { type: String },
        record: { type: Object },
        readonly: { type: Boolean, optional: true },
        required: { type: Boolean, optional: true },
        invisible: { type: Boolean, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this._chart = null;
        this._snapshot = null;

        onMounted(() => this._render());

        onPatched(() => {
            const data = this.props.record.data[this.props.name];
            if (data !== this._snapshot) {
                this._render();
            }
        });

        onWillUnmount(() => this._destroy());
    }

    _destroy() {
        if (this._chart) {
            try { this._chart.destroy(); } catch (_) {}
            this._chart = null;
        }
    }

    async _render() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        const raw = this.props.record.data[this.props.name];
        if (!raw) return;
        this._snapshot = raw;

        let config;
        try {
            config = JSON.parse(raw);
        } catch (e) {
            console.warn("[LiraCharts] JSON inválido en campo", this.props.name, e);
            return;
        }

        const Chart = await loadChart();
        if (!Chart) return;

        this._destroy();

        try {
            this._chart = new Chart(canvas.getContext("2d"), config);
        } catch (e) {
            console.error("[LiraCharts] Error al crear gráfica:", e);
        }
    }

    printChart() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        const imgData = canvas.toDataURL("image/png", 1.0);

        let title = "Gráfica financiera";
        try {
            const cfg = JSON.parse(this.props.record.data[this.props.name]);
            title = cfg?.options?.plugins?.title?.text || title;
        } catch (_) {}

        const fecha = new Date().toLocaleDateString("es-ES", {
            day: "2-digit", month: "long", year: "numeric",
        });

        const w = window.open("", "_blank", "width=950,height=720");
        if (!w) return;
        w.document.write(
            "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'/>" +
            "<title>" + title + "</title>" +
            "<style>" +
            "*{box-sizing:border-box;margin:0;padding:0}" +
            "body{font-family:Arial,sans-serif;background:#fff;padding:32px}" +
            ".hdr{border-bottom:3px solid #7c3aed;padding-bottom:12px;margin-bottom:24px}" +
            ".hdr h1{font-size:20px;color:#1e1b4b;font-weight:700}" +
            ".hdr p{font-size:12px;color:#6b7280;margin-top:4px}" +
            "img{max-width:100%;display:block}" +
            ".ftr{margin-top:20px;font-size:11px;color:#9ca3af;text-align:right}" +
            "</style></head><body>" +
            "<div class='hdr'><h1>" + title + "</h1>" +
            "<p>Generado el " + fecha + " — Análisis de Situación</p></div>" +
            "<img src='" + imgData + "'/>" +
            "<div class='ftr'>Lira Financial Suite</div>" +
            "<script>window.onload=function(){setTimeout(function(){window.print();},400);}<\/script>" +
            "</body></html>"
        );
        w.document.close();
    }
}

registry.category("fields").add("lira_chart", {
    component: LiraChartField,
    displayName: "Lira Chart",
    supportedTypes: ["text"],
    extractProps: ({ attrs }) => ({}),
});
