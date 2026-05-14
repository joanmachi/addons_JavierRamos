
from odoo import models, fields, api
from odoo.exceptions import AccessError, UserError, ValidationError
import logging


_logger = logging.getLogger(__name__)
class Venta(models.Model):
    _inherit = "sale.order"
    margen_beneficio = fields.Float(
        string="Margen de beneficio",
        default=1.5
    )
    total_cuestionario_fase_presupuesto = fields.Float(
        string="Total operaciones",
        copy=False
    )
    total_cuestionario_servicios_presupuesto = fields.Float(
        string="Total servicios",
        copy=False
    )
    total_cuestionario_material_presupuesto = fields.Float(
        string="Total material",
        copy=False
    )

    def action_quotation_send(self):
        _logger.info('----------- action_quotation_sent')
        for order in self:
            for linea in order.order_line:
                if linea.display_type == 'line_section' or linea.display_type == 'line_note':
                    continue
                cotizado = False
                if linea.product_template_id and linea.product_template_id.sale_order_line and linea.product_template_id.sale_order_line.id == linea.id:
                    cotizado = True
                if not cotizado:
                    raise UserError('Hay líneas sin cotizar')
        self.filtered(lambda so: so.state in ('draft', 'sent')).order_line._validate_analytic_distribution()
        lang = self.env.context.get('lang')

        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'email_notification_allow_footer': True,
            'proforma': self.env.context.get('proforma', False),
        }

        if len(self) > 1:
            ctx['default_composition_mode'] = 'mass_mail'
        else:
            ctx.update({
                'force_email': True,
                'model_description': self.with_context(lang=lang).type_name,
            })
            if not self.env.context.get('hide_default_template'):
                mail_template = self._find_mail_template()
                if mail_template:
                    ctx.update({
                        'default_template_id': mail_template.id,
                        'mark_so_as_sent': True,
                    })
                if mail_template and mail_template.lang:
                    lang = mail_template._render_lang(self.ids)[self.id]
            else:
                for order in self:
                    order._portal_ensure_token()

        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }
        if (
            self.env.context.get('check_document_layout')
            and not self.env.context.get('discard_logo_check')
            and self.env.is_admin()
            and not self.env.company.external_report_layout_id
        ):
            layout_action = self.env['ir.actions.report']._action_configure_external_report_layout(
                action,
            )
            # Need to remove this context for windows action
            action.pop('close_on_report_download', None)
            layout_action['context']['dialog_size'] = 'extra-large'
            return layout_action
        return action

    @api.onchange("margen_beneficio")
    def onchange_calcular_precio_venta(self):
        _logger.info('-------------- calcular_precio_venta')
        company = self.env.company
        
        for linea in self.order_line:
            _logger.info('-------------- for linea in self.order_line:')
            if self.margen_beneficio > 0:
                linea.price_unit = linea.coste_sin_beneficio * self.margen_beneficio
          

class VentaLinea(models.Model):
    _inherit = "sale.order.line"

    cantidad_caja = fields.Integer("Cajas")
    cantidad_en_caja = fields.Float(string="Cantidad en cajas")
    coste_sin_beneficio = fields.Float(string="Coste")
    cotizado = fields.Boolean(string="Cotizado", compute="_compute_cotizado")
    
    @api.depends("product_template_id")
    def _compute_cotizado(self):
        _logger.info('--------- _compute_cotizado')
        for linea in self:
            cotizado = False
            if linea.product_template_id and linea.product_template_id.sale_order_line and linea.product_template_id.sale_order_line.id == linea.id:
                cotizado = True

            linea.cotizado = cotizado


    @api.onchange("coste_sin_beneficio")
    def onchange_coste_sin_beneficio(self):
        for linea in self:
            if linea and linea.coste_sin_beneficio:
                if linea.order_id.margen_beneficio > 0:
                    linea.price_unit = linea.coste_sin_beneficio * linea.order_id.margen_beneficio
                else:
                    linea.price_unit = linea.coste_sin_beneficio

    
    @api.onchange("product_uom_qty")
    def onchange_calcular_precio_venta(self):
        _logger.info('--- onchange_calcular_precio_venta product_uom_qty')
    
    
        nuevo_precio = self.product_template_id.calcular_precio_venta(self.product_uom_qty)
        self.product_template_id.calcular_fecha_entrega()

        if nuevo_precio > 0:
            self.coste_sin_beneficio = nuevo_precio

            if self.order_id.margen_beneficio > 0:
                self.price_unit = self.coste_sin_beneficio * self.order_id.margen_beneficio
            else:
                self.price_unit = nuevo_precio
