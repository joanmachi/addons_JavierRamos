/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";

// ── Toggle acordeón de leyenda de ceros ─────────────────────────────────────
document.addEventListener("click", (e) => {
    const title = e.target.closest(".ld_legend_title");
    if (!title) return;
    title.closest(".ld_legend_ceros")?.classList.toggle("open");
}, true);

// Campos técnicos que NO deben aparecer en la tabla impresa
const HIDDEN_FIELDS = new Set([
    "id", "user_id", "create_uid", "create_date", "write_uid", "write_date",
    "display_name", "__last_update",
]);

function _formatValue(val, field) {
    if (val === false || val === null || val === undefined) return "";
    if (Array.isArray(val)) return val[1] || ""; // Many2one → display name
    if (field.type === "selection" && field.selection) {
        const found = field.selection.find((s) => s[0] === val);
        return found ? found[1] : val;
    }
    if (field.type === "float" || field.type === "monetary") {
        return Number(val).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (field.type === "integer") {
        return Number(val).toLocaleString("es-ES");
    }
    if (field.type === "date" && val) return val;
    if (field.type === "boolean") return val ? "✓" : "";
    return String(val);
}

class LiraPrintButton extends Component {
    static template = xml`
        <button class="ld_btn_pdf" t-on-click="printView" title="Descargar PDF de esta vista">
            <i class="fa fa-file-pdf-o"/> PDF
        </button>
    `;
    static props = {
        title: { type: String, optional: true },
        line_model: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
    }

    async _buildTable() {
        if (!this.props.line_model) return null;
        try {
            const fieldsInfo = await this.orm.call(this.props.line_model, "fields_get", [], {
                attributes: ["string", "type", "selection"],
            });
            const records = await this.orm.searchRead(
                this.props.line_model,
                [["user_id", "=", session.user_id || session.uid]],
                [],
                { limit: 500 },
            );
            if (!records.length) return null;

            // Columnas: orden por el de fields_get, excluyendo técnicos
            const cols = Object.keys(fieldsInfo).filter((fn) => !HIDDEN_FIELDS.has(fn) && !fn.startsWith("kpi_"));

            const wrap = document.createElement("div");
            wrap.id = "lira-print-table";

            const html = [];
            html.push("<table class='lira-print-table-inner'>");
            html.push("<thead><tr>");
            cols.forEach((fn) => {
                html.push("<th>" + (fieldsInfo[fn].string || fn) + "</th>");
            });
            html.push("</tr></thead><tbody>");
            records.forEach((r) => {
                html.push("<tr>");
                cols.forEach((fn) => {
                    html.push("<td>" + _formatValue(r[fn], fieldsInfo[fn]) + "</td>");
                });
                html.push("</tr>");
            });
            html.push("</tbody></table>");
            wrap.innerHTML = html.join("");
            return wrap;
        } catch (err) {
            console.warn("lira_print: no se pudo construir tabla de impresión", err);
            return null;
        }
    }

    async printView() {
        const viewTitle  = this.props.title || "Análisis de Situación";
        const companyName =
            session.company_name ||
            document.querySelector(".o_menu_brand")?.textContent?.trim() ||
            document.querySelector(".o_main_navbar .o_company_name")?.textContent?.trim() ||
            "Empresa";
        const fecha = new Date().toLocaleDateString("es-ES", {
            day: "2-digit", month: "long", year: "numeric",
        });
        const fechaCorta = new Date().toLocaleDateString("es-ES", {
            day: "2-digit", month: "2-digit", year: "numeric",
        }).replace(/\//g, "-");

        // Convertir canvases a imágenes para impresión correcta
        const replacements = [];
        document.querySelectorAll(".lira-chart-canvas-container canvas").forEach((canvas) => {
            try {
                const img = document.createElement("img");
                img.src = canvas.toDataURL("image/png", 1.0);
                img.className = "lira-canvas-print-img";
                canvas.parentNode.insertBefore(img, canvas);
                canvas.classList.add("lira-canvas-hidden-print");
                replacements.push({ canvas, img });
            } catch (_) {}
        });

        // Eliminar cabecera anterior si existe
        document.getElementById("lira-print-hdr")?.remove();
        document.getElementById("lira-print-table")?.remove();

        // Cabecera con empresa y fecha
        const hdr = document.createElement("div");
        hdr.id = "lira-print-hdr";
        hdr.innerHTML =
            "<div class='lira-print-hdr-inner'>" +
            "<div class='lira-print-hdr-company'>" + companyName + "</div>" +
            "<h1 class='lira-print-hdr-title'>" + viewTitle + "</h1>" +
            "<p class='lira-print-hdr-notice'>" +
            "Este documento es una imagen de la contabilidad a fecha <strong>" + fecha + "</strong>. " +
            "Los datos reflejan el estado en el momento de la generación del informe." +
            "</p>" +
            "</div>";
        document.body.prepend(hdr);

        // Construir tabla con los datos del modelo de línea (si hay)
        const table = await this._buildTable();
        if (table) {
            const sheet = document.querySelector(".o_form_sheet") || document.body;
            sheet.appendChild(table);
        }

        // Sugerir nombre de archivo
        const originalTitle = document.title;
        document.title = companyName + " - " + viewTitle + " - " + fechaCorta;

        await new Promise((r) => setTimeout(r, 200));
        window.print();

        // Restaurar
        document.title = originalTitle;
        hdr.remove();
        table?.remove();
        replacements.forEach(({ canvas, img }) => {
            canvas.classList.remove("lira-canvas-hidden-print");
            img.remove();
        });
    }
}

registry.category("view_widgets").add("lira_print_button", {
    component: LiraPrintButton,
    extractProps: ({ attrs }) => ({
        title: attrs.title || "",
        line_model: attrs.line_model || "",
    }),
});
