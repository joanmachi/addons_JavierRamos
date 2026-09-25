# -*- coding: utf-8 -*-
"""Stock por cliente: de quién es cada referencia y cuánto vale lo que hay.

Odoo no guarda el cliente en el stock: el inventario es por producto y
ubicación. En Javier Ramos, en cambio, cada pieza se codifica con un prefijo
de 4 dígitos del cliente (0612 = Stadler, 2175 = Hidragrup, 0584 = GBV...).
Aquí se aprovecha eso: el cliente de cada referencia se rellena solo con ese
prefijo y, si no lo tiene, con el cliente que más veces la ha comprado. Queda
en la ficha del producto y se puede corregir a mano; lo escrito a mano no se
vuelve a pisar.

Con el cliente en el producto, el stock ya se puede agrupar por cliente y
valorar, tanto a coste como a precio de venta (en las piezas fabricadas el
coste suele estar a cero, así que la columna de venta es la que dice algo).
"""
import logging
import re
from collections import defaultdict

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PREFIJO = re.compile(r"^\d{4}")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    lira_cliente_id = fields.Many2one(
        "res.partner", string="Cliente", index=True, ondelete="set null",
        help="Cliente al que pertenece la referencia. Se rellena solo a partir "
             "del prefijo de 4 dígitos de la referencia interna y, si no lo "
             "tiene, del cliente que más veces la ha comprado. Se puede cambiar "
             "a mano: a partir de ahí el automatismo ya no lo toca.",
    )
    lira_cliente_auto = fields.Boolean(
        string="Cliente puesto por el automatismo", default=False, copy=False,
        help="Marcado mientras el cliente lo haya puesto el automatismo. Al "
             "cambiarlo a mano se desmarca y queda fijo.",
    )

    lira_tipo_stock = fields.Selection(
        [("pieza", "Pieza de cliente"),
         ("materia_cliente", "Material y servicios para piezas de cliente"),
         ("materia", "Materia prima y compras"),
         ("consumible", "Consumibles y otros")],
        string="Tipo de stock", compute="_compute_lira_tipo_stock", store=True, index=True,
        help="Cómo se clasifica en los informes de stock, según el código (la "
             "referencia interna o, si no la tiene, el principio del nombre):\n"
             "· Pieza de cliente: solo dígitos (4 del cliente + la pieza), p. ej. 0612027318.\n"
             "· Material y servicios para piezas de cliente: el mismo número más letras, "
             "p. ej. 0612027318L (láser), X (acero), A (aluminio), PI (pintar), CI (cincado), "
             "AN (anodizado), S (soldar), M (mecanizado).\n"
             "· Materia prima y compras: sin código de cliente.\n"
             "· Consumibles y otros: categorías de consumibles, EPIs, ferretería, mercaderías o portes.",
    )
    lira_vendido = fields.Boolean(
        string="Con venta confirmada", default=False, copy=False,
        help="Tiene al menos un pedido confirmado o una factura. Lo mantiene el "
             "automatismo de clientes (cron diario / Recalcular clientes).",
    )

    CATEG_CONSUMIBLE = re.compile(
        r"CONSUMIBLE|EPIS|ACEITES|TALADRINA|FERRETERIA|MERCADER|PORTES|CONSUMO Y REPOSICI",
        re.IGNORECASE)

    @api.depends("default_code", "name", "categ_id", "categ_id.complete_name")
    def _compute_lira_tipo_stock(self):
        for tmpl in self:
            # Muchas piezas antiguas llevan la referencia en el NOMBRE
            # («01880509-CENTRADOR») y la referencia interna vacía: vale igual.
            code = (tmpl.default_code or tmpl.name or "").strip()
            token = re.split(r"[\s\-/]", code, 1)[0].upper()
            categ = tmpl.categ_id.complete_name or ""
            # La categoría de consumibles manda sobre el código: así un disco o
            # un guante con referencia numérica se saca de «piezas» cambiándolo
            # de categoría en la ficha.
            if self.CATEG_CONSUMIBLE.search(categ):
                tmpl.lira_tipo_stock = "consumible"
            elif re.fullmatch(r"\d{6,}", token):
                tmpl.lira_tipo_stock = "pieza"
            elif re.match(r"^\d{6,}[A-Z]", token):
                tmpl.lira_tipo_stock = "materia_cliente"
            else:
                tmpl.lira_tipo_stock = "materia"

    def write(self, vals):
        # Si alguien escribe el cliente a mano, deja de ser automático
        if "lira_cliente_id" in vals and not self.env.context.get("lira_auto"):
            vals = dict(vals, lira_cliente_auto=False)
        return super().write(vals)

    @api.model
    def _lira_mapas_cliente(self):
        """Quién compra cada cosa, contando pedidos confirmados y facturas.

        Devuelve dos diccionarios: prefijo de 4 dígitos -> cliente que más
        veces ha comprado referencias con ese prefijo, y variante -> cliente
        que más veces la ha comprado.
        """
        por_prefijo = defaultdict(lambda: defaultdict(int))
        por_producto = defaultdict(lambda: defaultdict(int))
        filas = []
        self.env.cr.execute("""
            SELECT pp.id,
                   COALESCE(pp.default_code, pt.name->>'es_ES', pt.name->>'en_US'),
                   COALESCE(rp.commercial_partner_id, rp.id),
                   COUNT(*)
              FROM sale_order_line sol
              JOIN sale_order so ON so.id = sol.order_id
              JOIN res_partner rp ON rp.id = so.partner_id
              JOIN product_product pp ON pp.id = sol.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE so.state IN ('sale', 'done')
             GROUP BY 1, 2, 3
        """)
        filas += self.env.cr.fetchall()
        self.env.cr.execute("""
            SELECT pp.id,
                   COALESCE(pp.default_code, pt.name->>'es_ES', pt.name->>'en_US'),
                   COALESCE(rp.commercial_partner_id, rp.id),
                   COUNT(*)
              FROM account_move_line aml
              JOIN account_move am ON am.id = aml.move_id
              JOIN res_partner rp ON rp.id = am.partner_id
              JOIN product_product pp ON pp.id = aml.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE am.move_type = 'out_invoice' AND am.state = 'posted'
             GROUP BY 1, 2, 3
        """)
        filas += self.env.cr.fetchall()
        for pid, code, partner, veces in filas:
            if not partner:
                continue
            por_producto[pid][partner] += veces
            if code and PREFIJO.match(code):
                por_prefijo[code[:4]][partner] += veces

        def gana(contador):
            return max(contador.items(), key=lambda kv: kv[1])[0] if contador else False

        return (
            {p: gana(v) for p, v in por_prefijo.items()},
            {p: gana(v) for p, v in por_producto.items()},
        )

    @api.model
    def _lira_ultimo_precio_venta(self):
        """Variante -> último precio unitario (con descuento) al que se vendió."""
        self.env.cr.execute("""
            SELECT DISTINCT ON (sol.product_id)
                   sol.product_id,
                   sol.price_unit * (1 - COALESCE(sol.discount, 0) / 100.0)
              FROM sale_order_line sol
              JOIN sale_order so ON so.id = sol.order_id
             WHERE so.state IN ('sale', 'done')
               AND sol.price_unit > 0
               AND sol.display_type IS NULL
             ORDER BY sol.product_id, so.date_order DESC, sol.id DESC
        """)
        return dict(self.env.cr.fetchall())

    def _lira_asignar_cliente(self, forzar=False):
        """Rellena el cliente de las referencias y devuelve cuántas cambió.

        Sin forzar respeta lo puesto a mano: solo toca las vacías y las que
        había puesto el propio automatismo.
        """
        mapa_pref, mapa_prod = self._lira_mapas_cliente()
        ultimo_precio = self._lira_ultimo_precio_venta()
        plantillas = self if self else self.search([])
        cambiadas = 0
        for tmpl in plantillas:
            variantes = tmpl.product_variant_ids.ids
            vals_extra = {}
            # «Con venta confirmada» y, si la ficha no tiene precio de venta, el
            # último precio al que se vendió (petición del cliente, 18/09/2026)
            vendido = any(v in mapa_prod for v in variantes)
            if vendido != tmpl.lira_vendido:
                vals_extra["lira_vendido"] = vendido
            if not tmpl.list_price:
                precio = next((ultimo_precio[v] for v in variantes if ultimo_precio.get(v)), None)
                if precio:
                    vals_extra["list_price"] = precio
            if vals_extra:
                tmpl.with_context(lira_auto=True).write(vals_extra)
            if tmpl.lira_cliente_id and not tmpl.lira_cliente_auto and not forzar:
                continue
            cliente = False
            code = (tmpl.default_code or tmpl.name or "").strip()
            if PREFIJO.match(code):
                cliente = mapa_pref.get(code[:4], False)
            if not cliente:
                for variante in tmpl.product_variant_ids:
                    cliente = mapa_prod.get(variante.id)
                    if cliente:
                        break
            if cliente and tmpl.lira_cliente_id.id != cliente:
                tmpl.with_context(lira_auto=True).write({
                    "lira_cliente_id": cliente, "lira_cliente_auto": True,
                })
                cambiadas += 1
        return cambiadas

    @api.model
    def _cron_lira_asignar_cliente(self):
        """Cada noche: pone cliente a las referencias nuevas."""
        cambiadas = self._lira_asignar_cliente()
        _logger.info("Stock por cliente: %d referencias con cliente nuevo", cambiadas)

    @api.model
    def action_lira_recalcular_clientes(self):
        """Botón 'Recalcular clientes' de la pantalla Stock por cliente."""
        cambiadas = self._lira_asignar_cliente()
        sin_cliente = self.search_count([
            ("lira_cliente_id", "=", False), ("lira_tipo_stock", "=", "pieza"),
            ("qty_available", ">", 0),
        ])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Clientes recalculados",
                "message": (
                    "%d referencias han recibido cliente. Quedan %d piezas de "
                    "cliente con stock y sin cliente: se les puede poner a mano en "
                    "la ficha del producto." % (cambiadas, sin_cliente)
                ),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class StockQuant(models.Model):
    _inherit = "stock.quant"

    lira_cliente_id = fields.Many2one(
        "res.partner", string="Cliente", store=True, index=True, readonly=True,
        related="product_id.product_tmpl_id.lira_cliente_id",
        help="Cliente de la referencia, tomado de la ficha del producto.",
    )
    lira_categ_id = fields.Many2one(
        "product.category", string="Categoría", store=True, readonly=True,
        related="product_id.categ_id",
    )
    lira_tipo_stock = fields.Selection(
        related="product_id.product_tmpl_id.lira_tipo_stock", store=True, index=True,
        readonly=True, string="Tipo de stock",
    )
    lira_vendido = fields.Boolean(
        related="product_id.product_tmpl_id.lira_vendido", store=True, readonly=True,
        string="Con venta confirmada",
    )
    # Los unitarios no se suman al agrupar: la suma de costes unitarios de
    # 500 referencias no significa nada y confundía en el pie de cada cliente.
    lira_coste_unit = fields.Float(
        string="Coste unit. (€)", compute="_compute_lira_valores", store=True,
        digits=(16, 4), aggregator=None,
    )
    lira_pvp_unit = fields.Float(
        string="Precio venta unit. (€)", compute="_compute_lira_valores",
        store=True, digits=(16, 4), aggregator=None,
    )
    lira_valor_coste = fields.Float(
        string="Valor a coste (€)", compute="_compute_lira_valores", store=True,
        digits=(16, 2),
        help="Cantidad × coste de la ficha. Sale 0 en las referencias que no "
             "tienen coste informado, que hoy son la mayoría de las fabricadas.",
    )
    lira_valor_venta = fields.Float(
        string="Valor a venta (€)", compute="_compute_lira_valores", store=True,
        digits=(16, 2),
        help="Cantidad × precio de venta de la ficha.",
    )

    @api.depends("quantity", "product_id", "company_id",
                 "product_id.standard_price", "product_id.list_price")
    def _compute_lira_valores(self):
        for quant in self:
            producto = quant.product_id.with_company(
                quant.company_id or self.env.company)
            coste = producto.standard_price or 0.0
            venta = producto.list_price or 0.0
            quant.lira_coste_unit = coste
            quant.lira_pvp_unit = venta
            quant.lira_valor_coste = quant.quantity * coste
            quant.lira_valor_venta = quant.quantity * venta
