/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import MainComponent from "@stock_barcode/components/main";
import { onMounted, onWillUnmount } from "@odoo/owl";

patch(MainComponent.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            this._apuntsInjectFinJornadaBtn();
            this._apuntsObserver = new MutationObserver(() => {
                this._apuntsInjectFinJornadaBtn();
            });
            this._apuntsObserver.observe(document.body, { childList: true, subtree: true });
        });
        onWillUnmount(() => {
            if (this._apuntsObserver) {
                this._apuntsObserver.disconnect();
            }
        });
    },
    _apuntsInjectFinJornadaBtn() {
        const bar = document.querySelector(".apunts-action-bar");
        if (!bar || bar.querySelector(".apunts-fin-jornada-btn")) {
            return;
        }
        const btn = document.createElement("button");
        btn.className = "apunts-fichar-btn apunts-fin-jornada-btn";
        btn.style.cssText = "background:#dc3545;margin-left:8px;color:white;";
        btn.innerHTML = '<i class="fa fa-sign-out me-1"></i>FIN JORNADA';
        btn.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            this.openFinJornadaWizard();
        });
        bar.appendChild(btn);
    },
    async openFinJornadaWizard() {
        const empleado = this.env.model.empleadoElegido;
        const ctx = {};
        if (empleado && empleado.id) {
            const emp = await this.orm.read("hr.employee", [empleado.id], ["pin"]);
            if (emp && emp[0] && emp[0].pin) {
                ctx.default_pin = emp[0].pin;
            }
        }
        await this.env.services.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Fin de jornada",
                res_model: "apunts.fin.jornada.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: ctx,
            },
            {
                onClose: async () => {
                    if (this.env && this.env.model && this.env.model.refrescarDatos) {
                        await this.env.model.refrescarDatos();
                    }
                    if (this.env && this.env.model) {
                        this.env.model.selectedEmployee = null;
                        this.env.model.trigger && this.env.model.trigger("update");
                    }
                },
            },
        );
    },
});
