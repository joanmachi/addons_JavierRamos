# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    formacion_solo_validadas = fields.Boolean('Servir solo guías validadas',
                                              config_parameter='grupadoo_formacion.solo_validadas',
                                              help='En producción: el cliente solo ve las guías que ya validó.')
    formacion_enlace = fields.Char('Enlace público', compute='_compute_formacion_enlace')
    formacion_enlace_hay = fields.Boolean(compute='_compute_formacion_enlace')
    formacion_tablero_gaps = fields.Boolean('Tablero de avisos visible en el enlace público',
                                            config_parameter='grupadoo_formacion.tablero_gaps',
                                            help='Enciéndelo cuando quieras enseñar al cliente el seguimiento de sus avisos (y apágalo después).')
    formacion_menu_desarrollos = fields.Boolean(
        'Menú "Desarrollos" visible',
        help='Apágalo para OCULTAR el menú Desarrollos (los gaps en solo lectura) '
             'a todos los usuarios. El tablero del enlace público tiene su propio interruptor.')
    formacion_publico_dependiente = fields.Char(
        'Etiqueta del público 1', config_parameter='grupadoo_formacion.publico_dependiente',
        help='Cómo se llama al personal "de a pie" en este cliente: 🛒 Tienda, 🏭 Planta, 🚚 Reparto… '
             'Se ve en el visor, en las guías y en los filtros. Vacío = "🛒 Tienda".')
    formacion_publico_oficina = fields.Char(
        'Etiqueta del público 2', config_parameter='grupadoo_formacion.publico_oficina',
        help='El segundo público (normalmente 🗂️ Oficina). Vacío = "🗂️ Oficina".')
    formacion_email_consultor = fields.Char('Correo del consultor',
                                            config_parameter='grupadoo_formacion.email_consultor',
                                            help='Si está relleno: correo automático al consultor cada vez que el '
                                                 'cliente reporte que algo no funciona en una guía (gap), desde el '
                                                 'visor o desde el enlace público.')
    formacion_soporte = fields.Boolean('Soporte Grupadoo (al terminar el proyecto)',
                                       config_parameter='grupadoo_formacion.soporte',
                                       help='Añade "🛟 Necesito asistencia" en el visor y en el enlace público: '
                                            'el cliente abre tickets de incidencia que llegan por correo al '
                                            'helpdesk de Grupadoo con la guía/paso/pantalla exactos.')
    formacion_email_soporte = fields.Char('Correo del helpdesk de Grupadoo',
                                          config_parameter='grupadoo_formacion.email_soporte',
                                          help='La dirección del equipo de soporte que crea los tickets '
                                               '(el alias del equipo de Helpdesk en el Odoo de Grupadoo).')
    formacion_url_soporte = fields.Char('Portal de soporte (web)',
                                        config_parameter='grupadoo_formacion.url_soporte',
                                        help='El formulario web de respaldo, por si el correo del cliente falla.')

    def _compute_formacion_enlace(self):
        icp = self.env['ir.config_parameter'].sudo()
        base = icp.get_param('web.base.url') or ''
        token = icp.get_param('grupadoo_formacion.token_publico') or ''
        for rec in self:
            rec.formacion_enlace_hay = bool(token)
            rec.formacion_enlace = f"{base}/formacion/{token}" if token else 'Sin generar todavía'

    def action_formacion_regenerar_enlace(self):
        """Nuevo token: el enlace antiguo deja de funcionar al instante (como el quiosco de asistencias)."""
        import secrets
        self.env['ir.config_parameter'].sudo().set_param(
            'grupadoo_formacion.token_publico', secrets.token_urlsafe(12))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def get_values(self):
        res = super().get_values()
        menu = self.env.ref('grupadoo_formacion.menu_formacion_desarrollos',
                            raise_if_not_found=False)
        res['formacion_menu_desarrollos'] = bool(menu and menu.active)
        return res

    def set_values(self):
        super().set_values()
        # las etiquetas del público son labels de un Selection: vaciar la caché
        # para que el cambio se vea sin reiniciar
        self.env.registry.clear_cache()
        menu = self.env.ref('grupadoo_formacion.menu_formacion_desarrollos',
                            raise_if_not_found=False)
        if menu and menu.active != self.formacion_menu_desarrollos:
            menu.active = self.formacion_menu_desarrollos

    def action_formacion_abrir_enlace(self):
        token = self.env['ir.config_parameter'].sudo().get_param('grupadoo_formacion.token_publico')
        if not token:
            token = self.env['formacion.ficha']._token_publico()
        return {'type': 'ir.actions.act_url', 'target': 'new', 'url': f'/formacion/{token}'}

    def action_formacion_abrir_portal_soporte(self):
        url = self.env['ir.config_parameter'].sudo().get_param('grupadoo_formacion.url_soporte')
        if not url:
            raise UserError('No hay portal de soporte configurado.')
        return {'type': 'ir.actions.act_url', 'target': 'new', 'url': url}
