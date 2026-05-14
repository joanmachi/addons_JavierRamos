/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";

class LiraSalesSearchBar extends Component {
    static template = "lira_dashboard_contabilidad.LiraSalesSearchBar";

    static props = {
        id:       { type: String, optional: true },
        value:    { optional: true },
        update:   { type: Function, optional: true },
        record:   { type: Object },
        readonly: { type: Boolean, optional: true },
        // extra props that Odoo field framework may inject
        name:     { type: String, optional: true },
        fieldName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            inputText: "",
            dropdownOpen: false,
            minInput: 0,
        });
        this.searchInputRef = useRef("searchInput");
        this._boundDocClick = this._onDocClick.bind(this);
        onMounted(() => document.addEventListener("click", this._boundDocClick));
        onWillUnmount(() => document.removeEventListener("click", this._boundDocClick));
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    get searchText() { return this.props.record.data.search_text || ""; }
    get filterAbc()  { return this.props.record.data.filter_abc  || ""; }
    get minImporte() { return this.props.record.data.min_importe || 0;  }
    get numResultados() { return this.props.record.data.num_resultados || 0; }

    get facets() {
        const f = [];
        if (this.searchText) {
            f.push({ key: "text", label: this.searchText,          field: "search_text", reset: "" });
        }
        if (this.filterAbc) {
            f.push({ key: "abc",  label: `ABC: ${this.filterAbc}`, field: "filter_abc",  reset: "" });
        }
        if (this.minImporte > 0) {
            f.push({ key: "min",  label: `Mín: ${this.minImporte}€`, field: "min_importe", reset: 0 });
        }
        return f;
    }

    // ── DOM helpers ───────────────────────────────────────────────────────────

    focusInput() {
        this.searchInputRef.el?.focus();
    }

    _onDocClick() {
        if (this.state.dropdownOpen) {
            this.state.dropdownOpen = false;
        }
    }

    // ── Input handlers ────────────────────────────────────────────────────────

    onInput(ev) {
        this.state.inputText = ev.target.value;
    }

    async onKeydown(ev) {
        if (ev.key === "Enter") {
            const val = this.state.inputText.trim();
            this.state.inputText = "";
            if (this.searchInputRef.el) this.searchInputRef.el.value = "";
            if (val) {
                await this.props.record.update({ search_text: val });
            }
        } else if (ev.key === "Backspace" && !this.state.inputText) {
            const facets = this.facets;
            if (facets.length) {
                const last = facets[facets.length - 1];
                await this.props.record.update({ [last.field]: last.reset });
            }
        }
    }

    async removeFacet(facet) {
        await this.props.record.update({ [facet.field]: facet.reset });
    }

    // ── Dropdown ──────────────────────────────────────────────────────────────

    toggleDropdown(ev) {
        ev.stopPropagation();
        if (!this.state.dropdownOpen) {
            this.state.minInput = this.minImporte;
        }
        this.state.dropdownOpen = !this.state.dropdownOpen;
    }

    async applyAbc(val) {
        this.state.dropdownOpen = false;
        const next = this.filterAbc === val ? "" : val;
        await this.props.record.update({ filter_abc: next });
    }

    onMinInput(ev) {
        this.state.minInput = parseFloat(ev.target.value) || 0;
    }

    async onMinKeydown(ev) {
        if (ev.key === "Enter") {
            await this.applyMin(ev);
        }
    }

    async applyMin(ev) {
        if (ev && ev.stopPropagation) ev.stopPropagation();
        this.state.dropdownOpen = false;
        await this.props.record.update({ min_importe: this.state.minInput || 0 });
    }

    async clearAll(ev) {
        if (ev && ev.stopPropagation) ev.stopPropagation();
        this.state.dropdownOpen = false;
        this.state.inputText = "";
        this.state.minInput = 0;
        if (this.searchInputRef.el) this.searchInputRef.el.value = "";
        await this.props.record.update({ search_text: "", filter_abc: "", min_importe: 0 });
    }
}

registry.category("fields").add("lira_sales_searchbar", {
    component: LiraSalesSearchBar,
    extractProps({ attrs }) {
        return {};
    },
});
