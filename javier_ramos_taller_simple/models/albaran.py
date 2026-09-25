from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round

class AlbaranLinea(models.Model):
    _inherit = "stock.move"

    fabricacion = fields.Many2one(
        'mrp.production',
        string='Fabricación',
        related="purchase_line_id.fabricacion"
    )

    def apunts_of_etiqueta(self):
        """La orden de fabricación que va en la etiqueta de expedición de esta
        línea. Las líneas de salida casi nunca llevan la OF puesta (solo la
        heredan de compras), así que se busca: primero la OF enlazada al
        pedido de venta de la línea; si no, la última OF del producto
        (terminada o en curso; con parciales, el último tramo)."""
        self.ensure_one()
        if self.fabricacion:
            return self.fabricacion
        MO = self.env['mrp.production'].sudo()
        base = [('product_id', '=', self.product_id.id), ('state', '!=', 'cancel')]
        so = self.sale_line_id.order_id
        if so:
            for campo, valor in (('sale_line_id', self.sale_line_id.id), ('sale_id', so.id),
                                 ('x_studio_venta', so.id)):
                if campo in MO._fields:
                    mo = MO.search(base + [(campo, '=', valor)], order='id desc', limit=1)
                    if mo:
                        return mo
            if 'apunts_sale_line_ids' in MO._fields:
                mo = MO.search(base + [('apunts_sale_line_ids', 'in', [self.sale_line_id.id])], order='id desc', limit=1)
                if mo:
                    return mo
            mo = MO.search(base + [('origin', 'ilike', so.name)], order='id desc', limit=1)
            if mo:
                return mo
        return MO.search(base + [('state', 'in', ('done', 'to_close', 'progress', 'confirmed'))],
                         order='id desc', limit=1)


class AlbaranDevolucion(models.Model):
    _inherit = "stock.picking"

    ORIGENES_DEVOLUCION = [
        ('compras', 'Error de compras (pedimos mal)'),
        ('proveedor', 'Fallo del proveedor'),
        ('mal_estado', 'Mercancía en mal estado'),
    ]
    apunts_es_devolucion_proveedor = fields.Boolean(
        string="Es devolución a proveedor", compute="_compute_apunts_es_devolucion_proveedor",
        store=True,
        help="Albarán creado como devolución de una recepción y con destino el proveedor.",
    )
    apunts_origen_devolucion = fields.Selection(
        ORIGENES_DEVOLUCION, string="Origen de la devolución", copy=False, tracking=True,
        help="Por qué se devuelve la materia prima. Obligatorio al validar una "
             "devolución a proveedor (petición de Xavi/Cinthia, 22/09/2026).",
    )

    @api.depends('return_id', 'location_dest_id.usage')
    def _compute_apunts_es_devolucion_proveedor(self):
        for pk in self:
            pk.apunts_es_devolucion_proveedor = bool(pk.return_id) and pk.location_dest_id.usage == 'supplier'

    def button_validate(self):
        faltan = self.filtered(lambda p: p.apunts_es_devolucion_proveedor and not p.apunts_origen_devolucion)
        if faltan:
            raise UserError(
                "Antes de validar la devolución %s hay que indicar el «Origen de la devolución» "
                "(error de compras, fallo del proveedor o mercancía en mal estado)." % ", ".join(faltan.mapped('name')))
        return super().button_validate()
class AlbaranMoveLinea(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_properties(self, move_line=False, move=False):
        res = super(AlbaranMoveLinea,
                    self)._get_aggregated_properties(move_line=move_line, move=move)
        if move:
            res.update({
                "fabricacion": move.fabricacion.name,
            })
        else:
            res.update({
                "fabricacion": self.move_id.fabricacion.name,
            })
        return res




  