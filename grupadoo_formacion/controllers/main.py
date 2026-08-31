# -*- coding: utf-8 -*-
"""Enlace público del asistente de formación: /formacion/<token>.

Para compartir con el cliente SIN usuario de Odoo. El token vive en el parámetro
`grupadoo_formacion.token_publico` (se genera solo). Cada guía se sirve como un
manual completo (todos los pasos con sus capturas) y el cliente puede validar,
avisar de un gap o dejar un comentario desde la propia página.
"""
import base64
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FormacionPublico(http.Controller):

    def _fichas(self, token):
        return request.env['formacion.ficha']._fichas_publicas(token)

    @http.route('/formacion/<string:token>', type='http', auth='public', sitemap=False)
    def indice(self, token, **kw):
        fichas = self._fichas(token)
        if fichas is None:
            return request.not_found()
        areas = fichas.mapped('area_id').sorted(key=lambda a: (a.sequence, a.name or ''))
        tablero = request.env['ir.config_parameter'].sudo().get_param(
            'grupadoo_formacion.tablero_gaps') in ('1', 'True')
        return request.render('grupadoo_formacion.pagina_indice', {
            'token': token, 'areas': areas, 'fichas': fichas, 'msg': kw.get('msg', ''),
            'tablero': tablero,
        })

    @http.route('/formacion/<string:token>/guia/<string:id_tecnico>', type='http', auth='public', sitemap=False)
    def guia(self, token, id_tecnico, **kw):
        fichas = self._fichas(token)
        if fichas is None:
            return request.not_found()
        ficha = fichas.filtered(lambda f: f.id_tecnico == id_tecnico)
        if not ficha:
            return request.not_found()
        ficha = ficha[0]
        adjuntos = {a.nombre: a.id for a in ficha.adjunto_ids}
        Ficha = request.env['formacion.ficha']
        MD = Ficha._md_html
        con_captura = Ficha._pasos_con_captura(ficha.paso_ids)
        soporte = Ficha._soporte_conf()
        return request.render('grupadoo_formacion.pagina_guia', {
            'token': token, 'ficha': ficha, 'msg': kw.get('msg', ''),
            'soporte': soporte['activo'], 'url_soporte': soporte['url'],
            'gaps_abiertos': len(ficha.gap_ids.filtered(lambda g: g.estado == 'abierto')),
            'cuando': MD(ficha.cuando, adjuntos, token),
            'antes': MD(ficha.antes, adjuntos, token),
            'si_mal': MD(ficha.si_mal, adjuntos, token),
            'escalar': MD(ficha.escalar, adjuntos, token),
            'pasos': [{'n': p.n, 'html': MD(p.texto, adjuntos, token), 'id': p.id,
                       'tiene_captura': p.id in con_captura} for p in ficha.paso_ids.sorted('sequence')],
        })

    @http.route('/formacion/<string:token>/avisos', type='http', auth='public', sitemap=False)
    def avisos(self, token, **kw):
        fichas = self._fichas(token)
        if fichas is None:
            return request.not_found()
        icp = request.env['ir.config_parameter'].sudo()
        if icp.get_param('grupadoo_formacion.tablero_gaps') not in ('1', 'True'):
            return request.not_found()
        # TODOS los avisos del cliente, aunque la guía esté oculta con "solo validadas":
        # si no, su aviso recién enviado desaparecería del seguimiento delante de sus ojos
        gaps = request.env['formacion.gap'].sudo().search(
            [('ficha_id.es_plantilla', '=', False)])
        columnas = [
            ('abierto', '📬 Recibidos', 'Los tenemos y estamos en ello.'),
            ('corregido', '✅ Corregidos', 'La guía ya está arreglada.'),
            ('descartado', '🗂 No procede', 'Revisados y no aplican (te contamos por qué).'),
        ]
        return request.render('grupadoo_formacion.pagina_avisos', {
            'token': token,
            'columnas': [{'clave': cl, 'titulo': ti, 'sub': su,
                          'gaps': gaps.filtered(lambda g: g.estado == cl)}
                         for cl, ti, su in columnas],
        })

    # ---- imágenes (con el token como llave; el usuario público no tiene ACLs) ----
    def _imagen(self, token, modelo, res_id, campo):
        fichas = self._fichas(token)
        if fichas is None:
            return request.not_found()
        reg = request.env[modelo].sudo().browse(int(res_id)).exists()
        # solo imágenes de guías que se están sirviendo (no se enumeran ids de borradores)
        if not reg or reg.ficha_id.id not in fichas.ids:
            return request.not_found()
        dato = reg[campo]
        if not dato:
            return request.not_found()
        binario = base64.b64decode(dato)
        if binario.startswith(b'\xff\xd8'):
            mime = 'image/jpeg'
        elif binario.startswith(b'GIF8'):
            mime = 'image/gif'
        elif binario.startswith(b'RIFF'):
            mime = 'image/webp'
        else:
            mime = 'image/png'
        return request.make_response(binario, headers=[
            ('Content-Type', mime), ('Cache-Control', 'private, max-age=3600')])

    @http.route('/formacion/<string:token>/img/paso/<int:paso_id>', type='http', auth='public', sitemap=False)
    def img_paso(self, token, paso_id, **kw):
        return self._imagen(token, 'formacion.paso', paso_id, 'captura')

    @http.route('/formacion/<string:token>/img/adjunto/<int:adj_id>', type='http', auth='public', sitemap=False)
    def img_adjunto(self, token, adj_id, **kw):
        return self._imagen(token, 'formacion.adjunto', adj_id, 'imagen')

    # ---- acciones del cliente desde la página pública ----
    def _ficha_de(self, token, id_tecnico):
        fichas = self._fichas(token)
        if fichas is None:
            return None
        ficha = fichas.filtered(lambda f: f.id_tecnico == id_tecnico)
        return ficha[0] if ficha else None

    @http.route('/formacion/<string:token>/guia/<string:id_tecnico>/validar',
                type='http', auth='public', methods=['POST'], csrf=True, sitemap=False)
    def validar(self, token, id_tecnico, nombre='', observacion='', **kw):
        ficha = self._ficha_de(token, id_tecnico)
        if ficha is None or not nombre.strip():
            return request.not_found()
        if ficha.gap_ids.filtered(lambda g: g.estado == 'abierto'):
            return request.redirect(f'/formacion/{token}/guia/{id_tecnico}?msg=gaps')
        request.env['formacion.validacion'].sudo().create({
            'ficha_id': ficha.id, 'usuario': nombre.strip(),
            'login': 'enlace-publico', 'observacion': observacion.strip(),
        })
        ficha.sudo().write({'estado': 'validado', 'validado_por': nombre.strip(),
                            'fecha_validado': fields.Datetime.now()})
        return request.redirect(f'/formacion/{token}/guia/{id_tecnico}?msg=validada')

    @http.route('/formacion/<string:token>/guia/<string:id_tecnico>/gap',
                type='http', auth='public', methods=['POST'], csrf=True, sitemap=False)
    def gap(self, token, id_tecnico, texto='', paso_n='0', nombre='', **kw):
        ficha = self._ficha_de(token, id_tecnico)
        if ficha is None or not texto.strip():
            return request.not_found()
        try:
            n = int(paso_n or 0)
        except (TypeError, ValueError):
            n = 0
        gap = request.env['formacion.gap'].sudo().create({
            'ficha_id': ficha.id, 'descripcion': texto.strip(),
            'paso_n': n or False,
            'reportado_por': nombre.strip() or 'Enlace público',
        })
        if ficha.estado == 'validado':
            ficha.sudo().write({'estado': 'en_validacion'})
        request.env['formacion.ficha'].sudo()._avisar_consultor_gap(gap)
        return request.redirect(f'/formacion/{token}/guia/{id_tecnico}?msg=gap')

    @http.route('/formacion/<string:token>/guia/<string:id_tecnico>/asistencia',
                type='http', auth='public', methods=['POST'], csrf=True, sitemap=False)
    def asistencia(self, token, id_tecnico, texto='', paso_n='0', nombre='', email='', urgencia='media', **kw):
        """Ticket de incidencia hacia el helpdesk de Grupadoo (soporte post-proyecto)."""
        ficha = self._ficha_de(token, id_tecnico)
        if ficha is None or not texto.strip():
            return request.not_found()
        try:
            n = int(paso_n or 0)
        except (TypeError, ValueError):
            n = 0
        r = request.env['formacion.ficha'].sudo()._enviar_ticket(
            ficha, n, texto,
            urgencia if urgencia in ('baja', 'media', 'alta') else 'media',
            nombre.strip() or 'Enlace público', email.strip())
        msg = 'asistencia' if r.get('ok') else 'asistencia_error'
        return request.redirect(f'/formacion/{token}/guia/{id_tecnico}?msg={msg}')

    @http.route('/formacion/<string:token>/guia/<string:id_tecnico>/comentario',
                type='http', auth='public', methods=['POST'], csrf=True, sitemap=False)
    def comentario(self, token, id_tecnico, texto='', nombre='', **kw):
        ficha = self._ficha_de(token, id_tecnico)
        if ficha is None or not texto.strip():
            return request.not_found()
        request.env['formacion.comentario'].sudo().create({
            'ficha_id': ficha.id, 'texto': texto.strip(),
            'autor': nombre.strip() or 'Enlace público', 'origen': 'publico',
        })
        return request.redirect(f'/formacion/{token}/guia/{id_tecnico}?msg=comentario')
