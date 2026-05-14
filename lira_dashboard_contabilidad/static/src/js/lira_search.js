/** @odoo-module **/

// Búsqueda y agrupación inline para tablas del dashboard Lira
// Convierte .ld_searchbar_mock en un buscador interactivo real sin abrir nueva ventana

function initLiraSearchBar(mock) {
    mock.setAttribute('data-lira-init', '1');

    // Buscar el campo one2many adyacente
    let listEl = mock.nextElementSibling;
    while (listEl && !listEl.classList.contains('o_field_one2many')) {
        listEl = listEl.nextElementSibling;
    }
    if (!listEl) return;

    // Vaciar el mock y construir la UI
    mock.innerHTML = '';
    const inner = document.createElement('div');
    inner.className = 'ld_sb_inner';

    const ico = document.createElement('i');
    ico.className = 'fa fa-search ld_sb_ico_search';

    const inp = document.createElement('input');
    inp.type = 'text';
    inp.placeholder = 'Buscar en esta tabla...';
    inp.className = 'ld_sb_input';
    inp.setAttribute('autocomplete', 'off');

    const clr = document.createElement('button');
    clr.type = 'button';
    clr.className = 'ld_sb_clear';
    clr.title = 'Limpiar búsqueda';
    clr.textContent = '✕';
    clr.style.display = 'none';

    const sep = document.createElement('span');
    sep.className = 'ld_sb_vsep';

    const grpLabel = document.createElement('span');
    grpLabel.className = 'ld_sb_grp_label';
    grpLabel.textContent = 'Agrupar:';

    const grp = document.createElement('select');
    grp.className = 'ld_sb_groupby';

    const car = document.createElement('i');
    car.className = 'fa fa-caret-down ld_sb_ico_caret';

    inner.append(ico, inp, clr, sep, grpLabel, grp, car);
    mock.appendChild(inner);

    // Poblar opciones de agrupación desde las cabeceras de columna
    function populateGroupby() {
        const ths = Array.from(listEl.querySelectorAll('thead th')).filter(th => {
            const cls = th.className;
            return !cls.includes('o_list_actions') &&
                   !cls.includes('o_list_selection') &&
                   !cls.includes('o_list_optional') &&
                   !cls.includes('o_handle') &&
                   th.textContent.trim().length > 0;
        });
        if (!ths.length) return;
        const prev = grp.value;
        grp.innerHTML = '<option value="">Sin agrupar</option>';
        ths.forEach((th, i) => {
            const label = (th.querySelector('span:not(.o_column_info)') || th).textContent.trim();
            if (!label) return;
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = label;
            grp.appendChild(opt);
        });
        if (prev) grp.value = prev;
    }

    // Filtrar filas por texto
    function filterRows() {
        const term = inp.value.toLowerCase().trim();
        clr.style.display = term ? '' : 'none';
        listEl.querySelectorAll('tbody tr.o_data_row').forEach(row => {
            const visible = !term || row.textContent.toLowerCase().includes(term);
            row.style.display = visible ? '' : 'none';
        });
    }

    // Agrupar filas por columna
    let grouped = false;
    function applyGroupBy() {
        const tbody = listEl.querySelector('tbody');
        if (!tbody) return;

        tbody.querySelectorAll('.ld_group_row').forEach(r => r.remove());

        const allRows = Array.from(tbody.querySelectorAll('tr.o_data_row'));
        allRows.forEach(r => r.style.display = '');
        grouped = false;

        if (!grp.value) { filterRows(); return; }

        const colIdx = parseInt(grp.value);
        const numCols = listEl.querySelectorAll('thead th').length;
        grouped = true;

        const groups = new Map();
        allRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            const cell = cells[colIdx];
            const key = cell ? (cell.textContent.trim() || '—') : '—';
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(row);
        });

        const sorted = Array.from(groups.entries()).sort(([a], [b]) =>
            a.localeCompare(b, 'es', { numeric: true })
        );

        allRows.forEach(r => tbody.removeChild(r));

        sorted.forEach(([key, rows]) => {
            const hdr = document.createElement('tr');
            hdr.className = 'ld_group_row';
            const td = document.createElement('td');
            td.colSpan = numCols;
            td.className = 'ld_group_header';
            td.innerHTML =
                '<i class="fa fa-folder-open-o me-1"></i>' +
                '<strong>' + (key || '(vacío)') + '</strong>' +
                ' <span class="ld_group_count">' + rows.length + ' filas</span>';
            hdr.appendChild(td);
            tbody.appendChild(hdr);
            rows.forEach(r => tbody.appendChild(r));
        });

        filterRows();
    }

    inp.addEventListener('input', filterRows);
    clr.addEventListener('click', () => {
        inp.value = '';
        grp.value = '';
        applyGroupBy();
    });
    grp.addEventListener('change', applyGroupBy);

    setTimeout(populateGroupby, 400);

    new MutationObserver(() => {
        populateGroupby();
        if (!grouped) filterRows();
    }).observe(listEl, { childList: true, subtree: true });
}

// Todo el código de observación del DOM se ejecuta DENTRO de DOMContentLoaded
// para garantizar que document.body existe cuando se llama a observe().
// NUNCA llamar a MutationObserver.observe() ni document.querySelectorAll()
// en el top-level de un /** @odoo-module **/ porque el bundle se ejecuta
// antes de que el DOM esté listo y document.body es null → blank page.
document.addEventListener('DOMContentLoaded', () => {
    // Inicializar los que ya estén en el DOM
    document.querySelectorAll('.ld_searchbar_mock:not([data-lira-init])').forEach(initLiraSearchBar);

    // Observar el body para inicializar los que aparezcan después (navegación SPA)
    if (document.body) {
        const globalObs = new MutationObserver(() => {
            document.querySelectorAll('.ld_searchbar_mock:not([data-lira-init])').forEach(initLiraSearchBar);
        });
        globalObs.observe(document.body, { childList: true, subtree: true });
    }
});
