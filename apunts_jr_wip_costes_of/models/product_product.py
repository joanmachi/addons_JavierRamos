from odoo import api, fields, models


_FUENTE_SEL = [
    ("po_recibida", "PO recibida"),
    ("po_confirmada", "PO confirmada"),
    ("bom", "BoM (fabricado)"),
    ("template", "Template (variante)"),
    ("seller", "Proveedor"),
    ("standard_price", "Ficha producto"),
    ("sin_coste", "Sin coste"),
]


class ProductProduct(models.Model):
    _inherit = "product.product"

    apunts_coste_real = fields.Monetary(
        string="Coste real",
        compute="_compute_apunts_coste_real",
        store=True,
        currency_field="currency_id",
    )
    apunts_coste_fuente = fields.Selection(
        selection=_FUENTE_SEL,
        string="Fuente coste",
        compute="_compute_apunts_coste_real",
        store=True,
    )
    apunts_valor_stock = fields.Monetary(
        string="Valor stock",
        compute="_compute_apunts_valor_stock",
        currency_field="currency_id",
        help="Coste real × cantidad disponible. Cuánto vale el stock total de este producto.",
    )
    apunts_comercializacion = fields.Selection(
        selection=[
            ("compra_venta", "Compra y venta"),
            ("solo_venta", "Solo venta"),
            ("solo_compra", "Solo compra"),
            ("ninguno", "Ni compra ni venta"),
        ],
        string="Compra y venta",
        compute="_compute_apunts_comercializacion",
        store=True,
        help="Clasificación según los campos del producto: se puede vender (sale_ok) y/o comprar (purchase_ok).",
    )

    @api.depends("sale_ok", "purchase_ok")
    def _compute_apunts_comercializacion(self):
        for product in self:
            if product.sale_ok and product.purchase_ok:
                product.apunts_comercializacion = "compra_venta"
            elif product.sale_ok:
                product.apunts_comercializacion = "solo_venta"
            elif product.purchase_ok:
                product.apunts_comercializacion = "solo_compra"
            else:
                product.apunts_comercializacion = "ninguno"

    @api.depends("apunts_coste_real", "qty_available")
    def _compute_apunts_valor_stock(self):
        for product in self:
            product.apunts_valor_stock = (product.apunts_coste_real or 0.0) * (product.qty_available or 0.0)

    def action_open_product_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.product",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.depends("standard_price", "seller_ids.price", "bom_ids")
    def _compute_apunts_coste_real_trigger(self):
        # Trigger del compute desde cambios en campos del producto. La invalidación por
        # cambios cross-model (POs, recepciones) la hace el override write/create de
        # purchase.order.line en este mismo módulo.
        return self._compute_apunts_coste_real()

    def _coste_desde_bom(self, depth=0):
        # Suma componentes BoM × precio resuelto + tiempos × costes_hora del workcenter.
        # Recursión limitada a 2 niveles para evitar bucles infinitos o cálculos lentos.
        if depth > 2:
            return 0.0
        self.ensure_one()
        bom = self.env["mrp.bom"]._bom_find(
            products=self, company_id=self.env.company.id
        ).get(self)
        if not bom:
            return 0.0
        total = 0.0
        bom_qty = bom.product_qty or 1.0
        for line in bom.bom_line_ids:
            comp = line.product_id
            comp_qty = (line.product_qty or 0.0) / bom_qty
            comp_price = comp.standard_price or 0.0
            if not comp_price:
                cr = self.env.cr
                cr.execute("""
                    SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    WHERE pol.product_id = %s AND po.state IN ('purchase','done') AND pol.qty_received > 0
                """, [comp.id])
                row = cr.fetchone()
                comp_price = float(row[0]) if row and row[0] else 0.0
            if not comp_price:
                comp_price = comp._coste_desde_bom(depth=depth + 1)
            total += comp_qty * comp_price
        for op in bom.operation_ids:
            wc = op.workcenter_id
            time_min = op.time_cycle_manual or 0.0
            hours = time_min / 60.0
            total += hours * ((wc.costs_hour or 0.0) + (wc.employee_costs_hour or 0.0))
        return total

    @api.depends("standard_price", "seller_ids.price")
    def _compute_apunts_coste_real(self):
        # Cascada de "coste real" prioritando compras reales sobre standard_price.
        # 1. Promedio ponderado POs recibidas (purchase/done qty_received > 0)
        # 2. Última PO en cualquier estado != cancel con price_unit > 0
        # 3. BoM activo (productos fabricados): suma componentes × precio + tiempos × coste_hora
        # 4. Promedio template (cubre variantes)
        # 5. seller_ids (precio proveedor configurado)
        # 6. standard_price del producto (último recurso)
        cr = self.env.cr
        for product in self:
            cr.execute("""
                SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                WHERE pol.product_id = %s AND po.state IN ('purchase','done') AND pol.qty_received > 0
            """, [product.id])
            row = cr.fetchone()
            avg = float(row[0]) if row and row[0] else 0.0
            if avg > 0:
                product.apunts_coste_real = avg
                product.apunts_coste_fuente = "po_recibida"
                continue
            cr.execute("""
                SELECT pol.price_unit FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                WHERE pol.product_id = %s AND po.state != 'cancel' AND pol.price_unit > 0
                ORDER BY po.date_order DESC NULLS LAST, po.id DESC LIMIT 1
            """, [product.id])
            row = cr.fetchone()
            last = float(row[0]) if row and row[0] else 0.0
            if last > 0:
                product.apunts_coste_real = last
                product.apunts_coste_fuente = "po_confirmada"
                continue
            bom_cost = product._coste_desde_bom()
            if bom_cost > 0:
                product.apunts_coste_real = bom_cost
                product.apunts_coste_fuente = "bom"
                continue
            tmpl_id = product.product_tmpl_id.id if product.product_tmpl_id else 0
            if tmpl_id:
                cr.execute("""
                    SELECT SUM(pol.price_unit * pol.qty_received) / NULLIF(SUM(pol.qty_received), 0)
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    JOIN product_product pp ON pp.id = pol.product_id
                    WHERE pp.product_tmpl_id = %s AND po.state IN ('purchase','done') AND pol.qty_received > 0
                """, [tmpl_id])
                row = cr.fetchone()
                v = float(row[0]) if row and row[0] else 0.0
                if v > 0:
                    product.apunts_coste_real = v
                    product.apunts_coste_fuente = "template"
                    continue
            seller_price = 0.0
            sellers = product.seller_ids.sorted(key=lambda s: (s.sequence or 99, -(s.id or 0)))
            for s in sellers:
                if s.price and s.price > 0:
                    seller_price = s.price
                    break
            if seller_price > 0:
                product.apunts_coste_real = seller_price
                product.apunts_coste_fuente = "seller"
                continue
            if product.standard_price:
                product.apunts_coste_real = product.standard_price
                product.apunts_coste_fuente = "standard_price"
                continue
            product.apunts_coste_real = 0.0
            product.apunts_coste_fuente = "sin_coste"
