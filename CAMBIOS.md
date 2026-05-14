# Registro de modificaciones - Odoo 18 Javier Ramos

---

## [001] Columna Fecha Vencimiento en lista de facturas

**Fecha:** 2026-05-14  
**Módulo:** `javier_ramos_pedidos`  
**Ficheros modificados:**
- `javier_ramos_pedidos/views/factura.xml` — vista lista (record id: `account_move_tree_view_inherit_date_due`)
- `javier_ramos_pedidos/models/account_move.py` — campo relacionado `invoice_due_date_display`
- `javier_ramos_pedidos/models/__init__.py` — import del nuevo modelo

**Vista afectada:** Contabilidad > Facturas y Contabilidad > Facturas de proveedores (lista)

**Qué hace:**  
Añade una columna "Fecha Vencimiento" en formato fecha junto a la columna existente de días restantes (`remaining_days`). Usa un campo relacionado `invoice_due_date_display` → `invoice_date_due` para poder mostrar ambas columnas a la vez.

**Para aplicar cambios:**
```
docker exec odoo_javierramos_local-odoo-1 odoo -d javierramoslocal --update=javier_ramos_pedidos --stop-after-init
docker restart odoo_javierramos_local-odoo-1
```

---
