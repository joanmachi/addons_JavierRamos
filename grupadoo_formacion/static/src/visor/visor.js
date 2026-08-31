/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, onWillUnmount, markup } from "@odoo/owl";

// Mini-markdown de las guías: negrita, cursiva, código y saltos. Nada más.
function md(texto) {
    if (!texto) { return ""; }
    let t = texto
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
        .replace(/\*([^*\n]+)\*/g, "<i>$1</i>")
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/^\s*[-•]\s+(.*)$/gm, "<span class='ff-li'>• $1</span>")
        .replace(/\n/g, "<br/>");
    return markup(t);
}

// "Devolución" tiene que encontrarse escribiendo "devolucion": sin acentos y en minúsculas
function norm(texto) {
    return (texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export class FormacionVisor extends Component {
    static template = "grupadoo_formacion.Visor";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            fichas: [], areas: [], q: "", publico: "ambas", cargado: false,
            soporte: false, urlSoporte: "",
            areaSel: null, ficha: null, paso: -1,  // -1 = portada de la ficha; 0..n-1 = pasos; n = final
            gapForm: false, gapTexto: "", gapPaso: 0, gapGracias: false, gapError: "", validaMsg: "",
            comForm: false, comTexto: "", comGracias: false, comError: "",
            tkForm: false, tkTexto: "", tkPaso: 0, tkUrg: "media", tkGracias: false, tkError: "",
        });
        onWillStart(async () => {
            const datos = await this.orm.call("formacion.ficha", "datos_visor", []);
            this.state.fichas = datos.fichas;
            this.state.areas = datos.areas;
            this.state.soporte = datos.soporte || false;
            this.state.urlSoporte = datos.url_soporte || "";
            this.state.cargado = true;
        });
        // atajos: Esc sale, ←/→ navegan pasos, Enter empieza (como el asistente web original)
        this._tecla = (ev) => this.tecla(ev);
        onMounted(() => document.addEventListener("keydown", this._tecla));
        onWillUnmount(() => document.removeEventListener("keydown", this._tecla));
    }

    tecla(ev) {
        const tag = (ev.target && ev.target.tagName) || "";
        if (tag === "INPUT" || tag === "TEXTAREA") {
            if (ev.key === "Escape") { ev.target.blur(); }
            return;
        }
        if (ev.key === "Escape") {
            if (this.state.gapForm) { this.state.gapForm = false; }
            else if (this.state.comForm) { this.state.comForm = false; }
            else if (this.state.tkForm) { this.state.tkForm = false; }
            else if (this.state.ficha) { this.cerrarFicha(); }
            return;
        }
        if (!this.state.ficha || this.state.gapForm || this.state.comForm || this.state.tkForm) { return; }
        if (ev.key === "ArrowRight" && this.state.paso >= 0 && !this.enFinal) { this.siguiente(); }
        else if (ev.key === "ArrowLeft" && this.state.paso > 0) { this.anterior(); }
        else if (ev.key === "Enter" && this.state.paso === -1 && this.state.ficha.pasos.length) { this.empezar(); }
    }

    md(t) { return md(t); }
    // secciones con imágenes {{img:nombre}} -> <img> del adjunto (backend autenticado)
    mdF(texto) {
        const adj = (this.state.ficha && this.state.ficha.adjuntos) || {};
        let t = texto || "";
        for (const [nombre, id] of Object.entries(adj)) {
            t = t.split(`{{img:${nombre}}}`).join(`\u0000IMG${id}\u0000`);
        }
        let html = String(md(t));
        html = html.replace(/\u0000IMG(\d+)\u0000/g,
            "<img class='ff-secimg' src='/web/image/formacion.adjunto/$1/imagen' alt=''/>");
        return markup(html);
    }

    // ---- home ----
    setPublico(p) { this.state.publico = p; this.state.areaSel = null; this.state.q = ""; }
    onSearch(ev) { this.state.q = ev.target.value; }
    abrirArea(id) { this.state.areaSel = this.state.areaSel === id ? null : id; this.state.q = ""; }

    get delPublico() {
        if (this.state.publico === "ambas") { return this.state.fichas; }
        return this.state.fichas.filter((f) => f.publico === this.state.publico);
    }
    get resultados() {
        const q = norm(this.state.q.trim());
        if (!q) { return []; }
        const palabras = q.split(/\s+/).filter(Boolean);
        const puntuadas = [];
        for (const f of this.delPublico) {
            const titulo = norm(f.titulo);
            const alias = f.alias.map(norm);
            const area = norm(f.area);
            const todo = `${titulo} ${alias.join(" ")} ${area}`;
            if (!palabras.every((p) => todo.includes(p))) { continue; }
            let puntos = 0;
            for (const p of palabras) {
                if (titulo.startsWith(p)) { puntos += 4; }
                else if (titulo.includes(p)) { puntos += 3; }
                if (alias.some((a) => a.includes(p))) { puntos += 2; }
                if (area.includes(p)) { puntos += 1; }
            }
            puntuadas.push([puntos, f]);
        }
        puntuadas.sort((a, b) => b[0] - a[0]);
        return puntuadas.slice(0, 8).map(([, f]) => f);
    }
    get areasVisibles() {
        const propias = new Set(this.delPublico.map((f) => f.area_id));
        return this.state.areas
            .filter((a) => propias.has(a.id))
            .map((a) => ({ ...a, n: this.delPublico.filter((f) => f.area_id === a.id).length }));
    }
    get fichasDelArea() {
        return this.delPublico.filter((f) => f.area_id === this.state.areaSel);
    }

    // ---- ficha / asistente ----
    abrirFicha(f) {
        this.state.ficha = f; this.state.paso = -1; this.state.validaMsg = "";
        this.state.gapForm = false; this.state.gapGracias = false; this.state.gapError = "";
        this.state.comForm = false; this.state.comGracias = false; this.state.comError = "";
        this.state.tkForm = false; this.state.tkGracias = false; this.state.tkError = "";
    }
    cerrarFicha() {
        this.state.ficha = null; this.state.paso = -1;
        this.state.gapForm = false; this.state.comForm = false; this.state.tkForm = false;
    }

    // ---- validación del cliente ----
    async aceptar() {
        const r = await this.orm.call("formacion.ficha", "aceptar_ficha", [this.state.ficha.id]);
        if (r.ok) {
            this.state.ficha.estado = "validado";
            this.state.validaMsg = "ok";
        } else {
            this.state.validaMsg = r.motivo || "No se pudo validar.";
        }
    }
    abrirGap(pasoN) { this.state.gapForm = true; this.state.gapPaso = pasoN || 0; this.state.gapTexto = ""; this.state.gapGracias = false; this.state.gapError = ""; }
    abrirCom() { this.state.comForm = true; this.state.comTexto = ""; this.state.comGracias = false; this.state.comError = ""; }
    cerrarCom() { this.state.comForm = false; }
    onComTexto(ev) { this.state.comTexto = ev.target.value; }
    async enviarCom() {
        if (!this.state.comTexto.trim()) { return; }
        const r = await this.orm.call("formacion.ficha", "comentar_ficha",
            [this.state.ficha.id, this.state.comTexto.trim()]);
        if (r.ok) { this.state.comForm = false; this.state.comGracias = true; }
        else { this.state.comError = r.motivo || "No se pudo enviar — inténtalo de nuevo."; }
    }
    cerrarGap() { this.state.gapForm = false; }
    onGapTexto(ev) { this.state.gapTexto = ev.target.value; }
    async enviarGap() {
        if (!this.state.gapTexto.trim()) { return; }
        const r = await this.orm.call("formacion.ficha", "reportar_gap",
            [this.state.ficha.id, this.state.gapTexto.trim(), this.state.gapPaso]);
        if (r.ok) {
            this.state.gapForm = false;
            this.state.gapGracias = true;
            this.state.ficha.gaps_abiertos = (this.state.ficha.gaps_abiertos || 0) + 1;
            if (this.state.ficha.estado === "validado") { this.state.ficha.estado = "en_validacion"; }
        } else {
            this.state.gapError = r.motivo || "No se pudo enviar — inténtalo de nuevo.";
        }
    }
    // ---- soporte post-proyecto: ticket de asistencia hacia Grupadoo ----
    // el MISMO botón "⚠️ algo no cuadra" cambia de función según la fase:
    // proyecto en construcción -> gap de la guía; proyecto cerrado (soporte ON) -> ticket a Grupadoo
    reportar(pasoN) {
        if (this.state.soporte) { this.abrirTk(pasoN); } else { this.abrirGap(pasoN); }
    }
    abrirTk(pasoN) {
        this.state.tkForm = true; this.state.tkPaso = pasoN || 0; this.state.tkTexto = "";
        this.state.tkUrg = "media"; this.state.tkGracias = false; this.state.tkError = "";
    }
    cerrarTk() { this.state.tkForm = false; }
    onTkTexto(ev) { this.state.tkTexto = ev.target.value; }
    setTkUrg(u) { this.state.tkUrg = u; }
    abrirPortal() { if (this.state.urlSoporte) { window.open(this.state.urlSoporte, "_blank"); } }
    async enviarTk() {
        if (!this.state.tkTexto.trim()) { return; }
        const r = await this.orm.call("formacion.ficha", "abrir_ticket",
            [this.state.ficha.id, this.state.tkPaso, this.state.tkTexto.trim(), this.state.tkUrg]);
        if (r.ok) {
            this.state.tkForm = false;
            this.state.tkGracias = true;
        } else {
            this.state.tkError = r.motivo || "No se pudo enviar — inténtalo de nuevo.";
        }
    }

    empezar() { this.state.paso = 0; }
    irAPaso(i) { this.state.paso = i; }
    // primera línea del paso sin marcadores markdown, para el índice de la portada
    lineaPaso(p) {
        return (p.texto || "").split("\n")[0].replace(/\*\*|\*|`/g, "").slice(0, 90);
    }
    siguiente() { this.state.paso += 1; }
    anterior() { this.state.paso -= 1; }
    get pasoActual() { return this.state.ficha ? this.state.ficha.pasos[this.state.paso] : null; }
    get enFinal() { return this.state.ficha && this.state.paso >= this.state.ficha.pasos.length; }
    get progreso() {
        const f = this.state.ficha;
        return f && f.pasos.length ? Math.round(((this.state.paso + 1) / f.pasos.length) * 100) : 0;
    }
}

registry.category("actions").add("grupadoo_formacion_visor", FormacionVisor);

// ══ Puerta de la zona de construcción: clave por SESIÓN (el logout la borra) ══
export class FormacionPuerta extends Component {
    static template = "grupadoo_formacion.Puerta";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ pedir: false, clave: "", mal: false });
        this.destino = (this.props.action.params || {}).destino || "grupadoo_formacion.action_formacion_fichas";
        onWillStart(async () => {
            const r = await this.orm.call("formacion.ficha", "puerta_estado", []);
            if (r.ok) { this.pasar(); } else { this.state.pedir = true; }
        });
    }

    pasar() {
        this.action.doAction(this.destino, { stackPosition: "replaceCurrentAction" });
    }
    onClave(ev) { this.state.clave = ev.target.value; }
    onKey(ev) { if (ev.key === "Enter") { this.entrar(); } }
    async entrar() {
        const r = await this.orm.call("formacion.ficha", "puerta_entrar", [this.state.clave.trim()]);
        if (r.ok) { this.pasar(); } else { this.state.mal = true; }
    }
}

registry.category("actions").add("grupadoo_formacion_puerta", FormacionPuerta);
