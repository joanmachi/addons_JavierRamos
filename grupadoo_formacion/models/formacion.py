# -*- coding: utf-8 -*-
import base64
import io
import logging
import os
import re
import unicodedata
import zipfile

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FormacionArea(models.Model):
    _name = 'formacion.area'
    _description = 'Área de formación (TPV, Inventario, Compras...)'
    _order = 'sequence, name'

    name = fields.Char('Área', required=True)
    sequence = fields.Integer(default=10)
    ficha_ids = fields.One2many('formacion.ficha', 'area_id', string='Guías')
    ficha_count = fields.Integer(compute='_compute_ficha_count')

    def _compute_ficha_count(self):
        datos = dict(self.env['formacion.ficha']._read_group(
            [('area_id', 'in', self.ids), ('es_plantilla', '=', False)], ['area_id'], ['__count']))
        for area in self:
            area.ficha_count = datos.get(area, 0)


class FormacionFicha(models.Model):
    _name = 'formacion.ficha'
    _description = 'Guía de formación paso a paso'
    _order = 'area_id, name'

    id_tecnico = fields.Char('Id técnico', index=True,
                             help='Identificador estable de la guía (p. ej. tpv-hacer-venta). '
                                  'Si lo dejas vacío se genera solo a partir del título.')
    name = fields.Char('Título', required=True)
    alias_text = fields.Text('Alias de búsqueda',
                             help='Uno por línea: cómo lo diría el usuario ("hacer un ticket", "cobrar")')
    area_id = fields.Many2one('formacion.area', string='Área', required=True)
    publico = fields.Selection([('dependiente', 'Planta'),
                                ('oficina', 'Oficina')],
                               default='dependiente', required=True)
    modulo_odoo = fields.Char('Módulo de Odoo', help='Módulo del que depende la pantalla (p. ej. point_of_sale)')
    es_custom = fields.Boolean('Depende de desarrollo a medida',
                               help='La pantalla depende de un módulo custom del cliente, no del Odoo estándar')
    version_odoo = fields.Char('Versión de Odoo', default='18.0')
    dispositivo = fields.Char('Dispositivo', help='Dónde se usa: terminal-tpv, ordenador...')
    es_plantilla = fields.Boolean('Es plantilla',
                                  help='Las plantillas no se muestran al cliente: son el punto de '
                                       'partida para crear guías nuevas ya estructuradas.')
    estado = fields.Selection([('borrador', 'Borrador'),
                               ('en_validacion', 'En validación (cliente)'),
                               ('validado', 'Validado')],
                              default='borrador', required=True, group_expand='_expand_estados')
    validado_por = fields.Char('Validado por')
    fecha_validado = fields.Datetime('Validada el')
    fecha_actualizado = fields.Date('Actualizado', help='Se actualiza solo al cambiar el contenido')
    validacion_ids = fields.One2many('formacion.validacion', 'ficha_id', string='Actas de validación')
    gap_ids = fields.One2many('formacion.gap', 'ficha_id', string='Gaps')
    gaps_abiertos = fields.Integer(compute='_compute_gaps_abiertos')
    adjunto_ids = fields.One2many('formacion.adjunto', 'ficha_id', string='Imágenes de secciones', copy=True)
    tiempo_ids = fields.One2many('formacion.tiempo', 'ficha_id', string='Horas de desarrollo')
    horas_total = fields.Float('Horas invertidas', compute='_compute_horas_total', compute_sudo=True)
    comentario_ids = fields.One2many('formacion.comentario', 'ficha_id', string='Comentarios del cliente')

    cuando = fields.Text('Cuándo se usa')
    antes = fields.Text('Antes de empezar')
    si_mal = fields.Text('Si algo va mal')
    escalar = fields.Text('Escalar')
    paso_ids = fields.One2many('formacion.paso', 'ficha_id', string='Pasos', copy=True)
    paso_count = fields.Integer(compute='_compute_paso_count')

    # Odoo 18: aquí la sintaxis es _sql_constraints (models.Constraint es de 19)
    _sql_constraints = [('id_tecnico_unico', 'unique(id_tecnico)',
                         'Ya existe una guía con ese id técnico.')]

    # Campos cuyo cambio invalida una guía ya aceptada (el acta antigua se conserva)
    CAMPOS_CONTENIDO = ('name', 'cuando', 'antes', 'si_mal', 'escalar', 'paso_ids')

    @api.model
    def _expand_estados(self, states, domain, order=None):
        return ['borrador', 'en_validacion', 'validado']

    def _compute_paso_count(self):
        for ficha in self:
            ficha.paso_count = len(ficha.paso_ids)

    def _compute_gaps_abiertos(self):
        for ficha in self:
            ficha.gaps_abiertos = len(ficha.gap_ids.filtered(lambda g: g.estado == 'abierto'))

    def _compute_horas_total(self):
        for ficha in self:
            ficha.horas_total = sum(ficha.tiempo_ids.mapped('horas'))

    # ------- id técnico: se genera solo, único siempre -------
    @api.model
    def _slugify(self, texto):
        t = unicodedata.normalize('NFD', texto or '')
        t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
        t = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')
        return t or 'guia'

    @api.model
    def _id_tecnico_libre(self, base, usados=None):
        base = base or 'guia'
        candidato, i = base, 2
        while (candidato in (usados or ())) or self.with_context(active_test=False).search_count(
                [('id_tecnico', '=', candidato)], limit=1):
            candidato = f'{base}-{i}'
            i += 1
        return candidato

    @api.model_create_multi
    def create(self, vals_list):
        usados = set()
        for vals in vals_list:
            if not vals.get('id_tecnico'):
                vals['id_tecnico'] = self._id_tecnico_libre(self._slugify(vals.get('name', '')), usados)
            usados.add(vals['id_tecnico'])
        return super().create(vals_list)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        default = default or {}
        for ficha, vals in zip(self, vals_list):
            if 'id_tecnico' not in default:
                base = re.sub(r'(-copia(-\d+)?)+$', '', ficha.id_tecnico or '') or 'guia'
                vals['id_tecnico'] = self._id_tecnico_libre(f'{base}-copia')
            if 'name' not in default:
                vals['name'] = f'{ficha.name} (copia)'
            if 'estado' not in default:
                vals['estado'] = 'borrador'
            vals['validado_por'] = default.get('validado_por', False)
            vals['fecha_validado'] = default.get('fecha_validado', False)
        return vals_list

    def action_crear_desde_plantilla(self):
        self.ensure_one()
        nueva = self.copy({'es_plantilla': False, 'name': self.name,
                           'id_tecnico': self._id_tecnico_libre(self._slugify(self.name))})
        return {'type': 'ir.actions.act_window', 'res_model': 'formacion.ficha',
                'res_id': nueva.id, 'view_mode': 'form', 'target': 'current'}

    def write(self, vals):
        # Nadie valida con gaps abiertos — ni arrastrando en el kanban
        if vals.get('estado') == 'validado':
            for ficha in self:
                if ficha.gap_ids.filtered(lambda g: g.estado == 'abierto'):
                    raise ValidationError(
                        f'"{ficha.name}" tiene gaps abiertos: corrígelos (o descártalos) antes de validar.')
            if 'validado_por' not in vals:
                # Validación manual desde el backend: también deja acta (con su origen claro)
                vals = dict(vals, validado_por=self.env.user.name,
                            fecha_validado=fields.Datetime.now())
                for ficha in self:
                    self.env['formacion.validacion'].sudo().create({
                        'ficha_id': ficha.id,
                        'usuario': self.env.user.name,
                        'login': self.env.user.login,
                        'observacion': 'Validación interna desde el backend (sin acta del cliente).',
                    })
        if any(c in vals for c in self.CAMPOS_CONTENIDO) and 'fecha_actualizado' not in vals:
            vals = dict(vals, fecha_actualizado=fields.Date.context_today(self))
        res = super().write(vals)
        # Tocar el contenido de una guía validada la devuelve a borrador (el acta queda como prueba)
        if any(c in vals for c in self.CAMPOS_CONTENIDO) and 'estado' not in vals:
            validadas = self.filtered(lambda f: f.estado == 'validado')
            if validadas:
                super(FormacionFicha, validadas).write({'estado': 'borrador'})
        return res

    def action_enviar_validacion(self):
        self.write({'estado': 'en_validacion'})

    # ------- lo que llama el visor del cliente -------
    @api.model
    def aceptar_ficha(self, ficha_id, observacion=''):
        """El cliente da por buena la guía: acta con firma+fecha y estado validado."""
        ficha = self.browse(int(ficha_id)).exists()
        if not ficha:
            return {'ok': False, 'motivo': 'La guía ya no existe.'}
        abiertos = ficha.gap_ids.filtered(lambda g: g.estado == 'abierto')
        if abiertos:
            return {'ok': False,
                    'motivo': f'Esta guía tiene {len(abiertos)} aviso(s) pendientes de corregir. '
                              'Cuando estén resueltos podrás validarla.'}
        self.env['formacion.validacion'].sudo().create({
            'ficha_id': ficha.id,
            'usuario': self.env.user.name,
            'login': self.env.user.login,
            'observacion': observacion or '',
        })
        ficha.sudo().write({'estado': 'validado',
                            'validado_por': self.env.user.name,
                            'fecha_validado': fields.Datetime.now()})
        return {'ok': True}

    @api.model
    def reportar_gap(self, ficha_id, texto, paso_n=0):
        """El cliente avisa de que algo no cuadra: queda registrado como GAP."""
        ficha = self.browse(int(ficha_id)).exists()
        if not ficha or not (texto or '').strip():
            return {'ok': False, 'motivo': 'Cuéntanos qué no cuadra (el texto está vacío).'}
        gap = self.env['formacion.gap'].sudo().create({
            'ficha_id': ficha.id,
            'paso_n': int(paso_n) or False,
            'descripcion': texto.strip(),
            'reportado_por': self.env.user.name,
        })
        # una guía con gap nuevo no puede quedarse como validada
        if ficha.estado == 'validado':
            ficha.sudo().write({'estado': 'en_validacion'})
        self._avisar_consultor_gap(gap)
        return {'ok': True}

    @api.model
    def _avisar_consultor_gap(self, gap):
        """Correo automático al consultor del proyecto cada vez que el cliente
        reporta un gap. Nunca rompe el alta del gap: si el correo falla, se loguea."""
        try:
            correo = (self.env['ir.config_parameter'].sudo().get_param(
                'grupadoo_formacion.email_consultor') or '').strip()
            if not correo or not gap:
                return
            from markupsafe import escape
            base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
            donde = f'{gap.ficha_id.area_id.name} / {gap.ficha_id.name}'
            if gap.paso_n:
                donde += f' — paso {gap.paso_n}'
            cuerpo = (
                f'<h3>⚠️ Nuevo gap del cliente</h3>'
                f'<p><b>{escape(gap.reportado_por or "Sin nombre")}</b> reporta en <b>{escape(donde)}</b>:</p>'
                f'<blockquote>{str(escape(gap.descripcion or "")).replace(chr(10), "<br/>")}</blockquote>'
                f'<p>Gestión: <a href="{escape(base)}/odoo/action-grupadoo_formacion.action_formacion_gaps">'
                f'Formación → Apunts → Gaps</a> · {escape(self.env.company.name or "")} · BD {escape(self.env.cr.dbname)}</p>')
            self.env['mail.mail'].sudo().create({
                'subject': f'[Formación] Gap: {donde}',
                'body_html': cuerpo,
                'email_to': correo,
            }).send(raise_exception=False)
        except Exception:
            _logger.warning('Formación: no se pudo avisar al consultor del gap %s',
                            gap and gap.id, exc_info=True)

    # ------- puerta de la zona de construcción (clave en sesión) -------
    @api.model
    def puerta_estado(self):
        """¿Esta sesión ya metió la clave de constructor? (el logout la borra sola)"""
        from odoo.http import request
        icp = self.env['ir.config_parameter'].sudo()
        if not (icp.get_param('grupadoo_formacion.clave_acceso') or '').strip():
            return {'ok': True}  # sin clave configurada, puerta abierta
        return {'ok': bool(request and request.session.get('formacion_constructor_ok'))}

    @api.model
    def puerta_entrar(self, clave):
        from odoo.http import request
        icp = self.env['ir.config_parameter'].sudo()
        guardada = (icp.get_param('grupadoo_formacion.clave_acceso') or '').strip()
        ok = not guardada or (clave or '').strip() == guardada
        if ok and request:
            request.session['formacion_constructor_ok'] = True
        return {'ok': ok}

    # ------- enlace público con token -------
    @api.model
    def _token_publico(self):
        icp = self.env['ir.config_parameter'].sudo()
        token = icp.get_param('grupadoo_formacion.token_publico')
        if not token:
            import secrets
            token = secrets.token_urlsafe(12)
            icp.set_param('grupadoo_formacion.token_publico', token)
        return token

    @api.model
    def _fichas_publicas(self, token):
        """Recordset de guías si el token es válido; None si no lo es.
        OJO: aquí solo se LEE el token (nunca se genera — esto corre en GETs
        públicos de solo lectura). Sin token configurado, el enlace está apagado.
        Con "solo validadas" se sirven también las EN VALIDACIÓN: si no, el gap
        del cliente haría desaparecer la guía (y su aviso) delante de sus ojos."""
        guardado = self.env['ir.config_parameter'].sudo().get_param(
            'grupadoo_formacion.token_publico')
        if not guardado or not token or token != guardado:
            return None
        dominio = [('es_plantilla', '=', False)]
        if self.env['ir.config_parameter'].sudo().get_param(
                'grupadoo_formacion.solo_validadas') == '1':
            dominio.append(('estado', 'in', ('validado', 'en_validacion')))
        return self.sudo().search(dominio)

    @api.model
    def _pasos_con_captura(self, pasos):
        """Ids de pasos que tienen captura SIN leer los binarios (fields.Image vive
        en ir.attachment: leer `captura` por paso descarga el fichero entero)."""
        if not pasos:
            return set()
        atts = self.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'formacion.paso'), ('res_field', '=', 'captura'),
             ('res_id', 'in', pasos.ids)], ['res_id'])
        return {a['res_id'] for a in atts}

    @api.model
    def _md_html(self, texto, adjuntos=None, token=''):
        """Mini-markdown a HTML seguro para las páginas públicas (espejo del md() del visor)."""
        from markupsafe import Markup, escape
        if not texto:
            return Markup('')
        t = str(escape(texto))
        for nombre, adj_id in (adjuntos or {}).items():
            t = t.replace('{{img:%s}}' % nombre,
                          '<img class="fp-secimg" src="/formacion/%s/img/adjunto/%s" alt=""/>' % (token, adj_id))
        t = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        t = re.sub(r'^\s*[-•]\s+(.*)$', r"<span class='fp-li'>• \1</span>", t, flags=re.M)
        t = t.replace('\n', '<br/>')
        return Markup(t)

    @api.model
    def comentar_ficha(self, ficha_id, texto):
        ficha = self.browse(int(ficha_id)).exists()
        if not ficha or not (texto or '').strip():
            return {'ok': False, 'motivo': 'El comentario está vacío.'}
        self.env['formacion.comentario'].sudo().create({
            'ficha_id': ficha.id, 'texto': texto.strip(),
            'autor': self.env.user.name, 'login': self.env.user.login, 'origen': 'visor',
        })
        return {'ok': True}

    # ------- soporte post-proyecto: tickets de asistencia hacia el Odoo de Grupadoo -------
    @api.model
    def _soporte_conf(self):
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'activo': icp.get_param('grupadoo_formacion.soporte') in ('1', 'True'),
            'email': (icp.get_param('grupadoo_formacion.email_soporte') or '').strip(),
            'url': (icp.get_param('grupadoo_formacion.url_soporte') or '').strip(),
        }

    @api.model
    def _enviar_ticket(self, ficha, paso_n, texto, urgencia, autor, email_autor):
        """Correo hacia el helpdesk de Grupadoo con TODO el contexto. El valor
        frente a un aviso normal: señala exactamente dónde está el error (área,
        guía, paso y el módulo de Odoo del que depende esa pantalla)."""
        from markupsafe import escape
        conf = self._soporte_conf()
        if not conf['activo'] or not conf['email']:
            return {'ok': False, 'motivo': 'El soporte no está activado en Ajustes → Formación.'}
        if not (texto or '').strip():
            return {'ok': False, 'motivo': 'Cuéntanos qué pasa (el texto está vacío).'}
        import odoo.release as release
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        empresa = self.env.company.name or ''
        urg = {'baja': '🟢 Baja', 'media': '🟡 Media', 'alta': '🔴 Alta'}.get(urgencia, '🟡 Media')
        donde = 'General (sin guía concreta)'
        if ficha:
            donde = f'{ficha.area_id.name} / {ficha.name}'
            if paso_n:
                donde += f' — paso {paso_n}'
        filas = [
            ('Empresa', empresa),
            ('Quién', f'{autor} <{email_autor}>' if email_autor else autor),
            ('Urgencia', urg),
            ('Dónde', donde),
        ]
        if ficha and ficha.modulo_odoo:
            filas.append(('Pantalla / módulo Odoo',
                          ficha.modulo_odoo + (' — desarrollo a medida' if ficha.es_custom else ' — estándar')))
        filas.append(('Odoo del cliente', f'{base} · BD {self.env.cr.dbname} · Odoo {release.version}'))
        cuerpo = ['<h3>🛟 Ticket de asistencia desde Formación</h3>',
                  '<table border="0" cellpadding="4">']
        cuerpo += [f'<tr><td style="color:#888">{escape(k)}</td><td><b>{escape(v)}</b></td></tr>'
                   for k, v in filas]
        cuerpo.append('</table><p><b>Descripción del cliente:</b></p>')
        cuerpo.append('<p>%s</p>' % str(escape(texto.strip())).replace('\n', '<br/>'))
        mail = self.env['mail.mail'].sudo().create({
            'subject': f'[Asistencia Odoo] {empresa} — {donde}',
            'body_html': ''.join(cuerpo),
            'email_to': conf['email'],
            'email_from': email_autor or self.env.company.email or False,
            'reply_to': email_autor or False,
        })
        mail.send(raise_exception=False)
        if mail.state != 'sent':
            return {'ok': False, 'url': conf['url'],
                    'motivo': 'No se ha podido enviar el correo de soporte (¿servidor de correo caído?). '
                              'Abre el portal de soporte o llámanos — tu texto queda guardado en los '
                              'correos del sistema y lo podemos reenviar.'}
        return {'ok': True}

    @api.model
    def abrir_ticket(self, ficha_id, paso_n, texto, urgencia='media'):
        """Ticket de asistencia desde el visor (usuario logueado del cliente)."""
        ficha = self.browse(int(ficha_id)).exists() if ficha_id else self.browse()
        return self._enviar_ticket(
            ficha, int(paso_n or 0), texto,
            urgencia if urgencia in ('baja', 'media', 'alta') else 'media',
            self.env.user.name, self.env.user.email or self.env.user.login)

    # ------- datos para el visor (una sola llamada) -------
    @api.model
    def datos_visor(self, clave=False):
        # La pantalla del cliente (Formaciones) va SIN clave; la clave protege la
        # puerta de construcción (ver puerta_*). `clave` se mantiene por compatibilidad.
        icp = self.env['ir.config_parameter'].sudo()
        solo_validadas = icp.get_param('grupadoo_formacion.solo_validadas') in ('1', 'True')
        dominio = [('es_plantilla', '=', False)]
        if solo_validadas:
            # también las en_validacion: el cliente tiene que poder re-validar tras un gap
            dominio.append(('estado', 'in', ('validado', 'en_validacion')))
        fichas = self.search(dominio)
        con_captura = self._pasos_con_captura(fichas.paso_ids)
        areas = fichas.area_id.sorted(key=lambda a: (a.sequence, a.name or ''))
        soporte = self._soporte_conf()

        def _hora_local(dt):
            if not dt:
                return ''
            return fields.Datetime.context_timestamp(self, dt).strftime('%d/%m/%Y %H:%M')

        return {
            'soporte': soporte['activo'],
            'url_soporte': soporte['url'],
            'areas': [{'id': a.id, 'nombre': a.name,
                       'n': len(fichas.filtered(lambda f: f.area_id == a))} for a in areas],
            'fichas': [{
                'id': f.id, 'id_tecnico': f.id_tecnico, 'titulo': f.name,
                'alias': [l.strip() for l in (f.alias_text or '').splitlines() if l.strip()],
                'area_id': f.area_id.id, 'area': f.area_id.name,
                'publico': f.publico, 'modulo': f.modulo_odoo or '',
                'custom': f.es_custom, 'estado': f.estado,
                'validado_por': f.validado_por or '', 'fecha_validado': _hora_local(f.fecha_validado),
                'gaps_abiertos': len(f.gap_ids.filtered(lambda g: g.estado == 'abierto')),
                'cuando': f.cuando or '', 'antes': f.antes or '',
                'si_mal': f.si_mal or '', 'escalar': f.escalar or '',
                'adjuntos': {a.nombre: a.id for a in f.adjunto_ids},
                'pasos': [{'n': p.n, 'texto': p.texto or '',
                           'captura': p.id in con_captura,
                           'url': f'/web/image/formacion.paso/{p.id}/captura'}
                          for p in f.paso_ids.sorted('sequence')],
            } for f in fichas],
        }

    # ------- importación (wizard ZIP, carpeta en disco o el repo web original) -------
    @api.model
    def importar_carpeta(self, ruta):
        """Importa desde disco: `ruta` puede ser el repo web original (contenido/fichas
        + public/capturas) o una carpeta plana con .md e imágenes."""
        ficheros = {}
        candidatos = [os.path.join(ruta, 'contenido', 'fichas'),
                      os.path.join(ruta, 'public', 'capturas'), ruta]
        for d in candidatos:
            if os.path.isdir(d):
                for nombre in os.listdir(d):
                    camino = os.path.join(d, nombre)
                    if os.path.isfile(camino) and nombre not in ficheros:
                        with open(camino, 'rb') as fh:
                            ficheros[nombre] = fh.read()
        return self._importar_ficheros(ficheros)

    @api.model
    def _importar_ficheros(self, ficheros):
        """Núcleo del importador. `ficheros` = {ruta/nombre: bytes}: los .md son
        guías; el resto, imágenes que se resuelven por nombre de fichero."""
        mds, imgs = {}, {}
        for ruta, dato in ficheros.items():
            base = os.path.basename(str(ruta).replace('\\', '/'))
            if not base or base.startswith('.') or '__MACOSX' in str(ruta):
                continue
            if base.lower().endswith('.md'):
                mds[base] = dato
            elif base.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                imgs.setdefault(base, dato)
        creadas = actualizadas = 0
        ids, avisos = [], []
        for nombre in sorted(mds):
            crudo = mds[nombre]
            if isinstance(crudo, bytes):
                crudo = crudo.decode('utf-8', errors='replace')
            meta, cuerpo = self._parse_frontmatter(crudo)
            cuerpo = re.sub(r'<!--[\s\S]*?-->', '', cuerpo).strip()
            id_tecnico = meta.get('id') or nombre[:-3]
            area = self.env['formacion.area'].search([('name', '=', meta.get('area', 'TPV'))], limit=1)
            if not area:
                area = self.env['formacion.area'].create({'name': meta.get('area', 'TPV')})
            modulo = meta.get('modulo', 'point_of_sale')
            alias = meta.get('alias') or []
            if isinstance(alias, str):  # "alias: cobrar" en línea (sin lista) — no trocearlo por letras
                alias = [alias]
            actualizado = meta.get('actualizado') or False
            if actualizado:
                try:
                    actualizado = fields.Date.to_date(str(actualizado))
                except ValueError:
                    avisos.append(f'{id_tecnico}: fecha "{actualizado}" no válida — se ignora')
                    actualizado = False
            # imágenes dentro de las secciones ANTES de escribir: un solo write
            # (si no, el segundo write des-validaba la guía recién importada)
            secciones, nombres_img = {}, []
            for campo, titulo in (('cuando', 'Cuándo se usa'), ('antes', 'Antes de empezar'),
                                  ('si_mal', 'Si algo va mal'), ('escalar', 'Escalar')):
                texto = self._seccion(cuerpo, titulo)
                if texto:
                    def _cambia(m):
                        base_img = os.path.basename(m.group(1))
                        nombres_img.append(base_img)
                        return '{{img:%s}}' % base_img
                    texto = re.sub(r'`?\s*!\[[^\]]*\]\(([^)]+)\)\s*`?', _cambia, texto)
                secciones[campo] = texto
            estado_md = 'validado' if meta.get('estado') == 'validado' else 'borrador'
            ficha = self.search([('id_tecnico', '=', id_tecnico)], limit=1)
            if estado_md == 'validado' and ficha and ficha.gap_ids.filtered(lambda g: g.estado == 'abierto'):
                avisos.append(f'{id_tecnico}: el MD dice "validado" pero tiene gaps abiertos — se deja en validación')
                estado_md = 'en_validacion'
            vals = {
                'id_tecnico': id_tecnico,
                'name': meta.get('titulo') or id_tecnico,
                'alias_text': '\n'.join(alias),
                'area_id': area.id,
                'publico': 'oficina' if meta.get('publico') == 'oficina' else 'dependiente',
                'modulo_odoo': modulo,
                'es_custom': not self._es_modulo_estandar(modulo),
                'version_odoo': str(meta.get('version_odoo', '18.0')),
                'dispositivo': meta.get('dispositivo', ''),
                'estado': estado_md,
                'validado_por': meta.get('validado_por', ''),
                'fecha_actualizado': actualizado,
                **secciones,
            }
            if ficha:
                ficha.paso_ids.unlink()
                ficha.adjunto_ids.unlink()
                ficha.write(vals)
                actualizadas += 1
            else:
                ficha = self.create(vals)
                creadas += 1
            ids.append(ficha.id)
            for base_img in dict.fromkeys(nombres_img):
                if base_img in imgs:
                    self.env['formacion.adjunto'].create({
                        'ficha_id': ficha.id, 'nombre': base_img,
                        'imagen': base64.b64encode(imgs[base_img])})
                else:
                    avisos.append(f'{id_tecnico}: la imagen "{base_img}" no viene en el ZIP')
            for seq, paso in enumerate(self._parse_pasos(cuerpo), start=1):
                pvals = {'ficha_id': ficha.id, 'sequence': seq, 'texto': paso['texto']}
                if paso.get('captura'):
                    base_img = os.path.basename(paso['captura'])
                    if base_img in imgs:
                        pvals['captura'] = base64.b64encode(imgs[base_img])
                        pvals['captura_nombre'] = base_img
                    else:
                        avisos.append(f'{id_tecnico}: la captura "{base_img}" (paso {seq}) no viene en el ZIP')
                self.env['formacion.paso'].create(pvals)
        return {'creadas': creadas, 'actualizadas': actualizadas, 'ids': ids, 'avisos': avisos}

    # ------- exportación: ZIP con los .md + capturas (ida y vuelta con el importador) -------
    def action_exportar_zip(self):
        if not self.env.user.has_group('grupadoo_formacion.group_formacion_constructor'):
            raise UserError('Solo el equipo constructor puede exportar guías.')
        fichas = self.filtered(lambda f: f.id_tecnico)
        if not fichas:
            raise UserError('No hay ninguna guía que exportar.')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            imagenes = {}
            for ficha in fichas:
                md = ficha._a_markdown(imagenes)
                z.writestr(f'fichas/{ficha.id_tecnico}.md', md)
            for nombre, dato in imagenes.items():
                z.writestr(f'capturas/{nombre}', dato)
        dato = buf.getvalue()  # fuera del with: el zip se cierra (y escribe su índice) antes de leerlo
        nombre_zip = f'{fichas.id_tecnico}.zip' if len(fichas) == 1 else 'guias_formacion.zip'
        attachment = self.env['ir.attachment'].create({
            'name': nombre_zip, 'datas': base64.b64encode(dato),
            'mimetype': 'application/zip',
            'res_model': 'formacion.ficha', 'res_id': fichas[0].id,
        })
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': f'/web/content/{attachment.id}?download=true'}

    def _a_markdown(self, imagenes):
        """Markdown de la guía en el formato que entiende `_importar_ficheros`.
        Las imágenes se acumulan en `imagenes` (nombre -> bytes) para el ZIP."""
        self.ensure_one()

        def _img(nombre, b64):
            if not b64:
                return None
            dato = base64.b64decode(b64)
            if nombre in imagenes and imagenes[nombre] != dato:
                nombre = f'{self.id_tecnico}-{nombre}'
            imagenes[nombre] = dato
            return nombre

        lineas = ['---', f'id: {self.id_tecnico}', f'titulo: "{self.name}"',
                  f'area: {self.area_id.name}', f'publico: {self.publico}',
                  f'modulo: {self.modulo_odoo or ""}', f'version_odoo: "{self.version_odoo or ""}"',
                  f'dispositivo: {self.dispositivo or ""}', f'estado: {self.estado}']
        if self.validado_por:
            lineas.append(f'validado_por: "{self.validado_por}"')
        if self.fecha_actualizado:
            lineas.append(f'actualizado: {self.fecha_actualizado}')
        alias = [l.strip() for l in (self.alias_text or '').splitlines() if l.strip()]
        if alias:
            lineas.append('alias:')
            lineas += [f'  - {a}' for a in alias]
        lineas += ['---', '']
        adjuntos = {a.nombre: a for a in self.adjunto_ids}
        for campo, titulo in (('cuando', 'Cuándo se usa'), ('antes', 'Antes de empezar')):
            texto = self[campo]
            if texto:
                for nombre, adj in adjuntos.items():
                    guardado = _img(nombre, adj.imagen)
                    if guardado:
                        texto = texto.replace('{{img:%s}}' % nombre, f'![{nombre}]({guardado})')
                lineas += [f'## {titulo}', '', texto, '']
        if self.paso_ids:
            lineas += ['## Pasos', '']
            for p in self.paso_ids.sorted('sequence'):
                texto = (p.texto or '').replace('\n', '\n   ')
                lineas.append(f'{p.n}. {texto}')
                if p.captura:
                    nombre = _img(p.captura_nombre or f'{self.id_tecnico}-paso-{p.n:02d}.png', p.captura)
                    if nombre:
                        lineas.append(f'   ![captura]({nombre})')
            lineas.append('')
        for campo, titulo in (('si_mal', 'Si algo va mal'), ('escalar', 'Escalar')):
            texto = self[campo]
            if texto:
                for nombre, adj in adjuntos.items():
                    guardado = _img(nombre, adj.imagen)
                    if guardado:
                        texto = texto.replace('{{img:%s}}' % nombre, f'![{nombre}]({guardado})')
                lineas += [f'## {titulo}', '', texto, '']
        return '\n'.join(lineas)

    @api.model
    def _es_modulo_estandar(self, modulo):
        # custom = prefijos de módulos a medida; configurable por parámetro (lista separada por comas)
        prefijos = (self.env['ir.config_parameter'].sudo().get_param(
            'grupadoo_formacion.prefijos_custom') or 'x_').split(',')
        prefijos = [p.strip() for p in prefijos if p.strip()]
        return not any((modulo or '').startswith(p) for p in prefijos)

    @staticmethod
    def _parse_frontmatter(crudo):
        crudo = crudo.replace('\r\n', '\n')
        m = re.match(r'^---\n([\s\S]*?)\n---\n?([\s\S]*)$', crudo)
        if not m:
            return {}, crudo
        meta, cuerpo = {}, m.group(2)
        clave = None
        for linea in m.group(1).splitlines():
            lista = re.match(r'^\s+-\s+(.*)$', linea)
            if lista and clave:
                meta.setdefault(clave, [])
                if isinstance(meta[clave], list):
                    meta[clave].append(lista.group(1).strip())
                continue
            kv = re.match(r'^([\w_]+):\s*(.*)$', linea)
            if kv:
                clave, valor = kv.group(1), kv.group(2).strip().strip('"')
                meta[clave] = [] if valor == '' and clave == 'alias' else valor
        return meta, cuerpo

    @staticmethod
    def _seccion(cuerpo, titulo):
        m = re.search(rf'##\s+{re.escape(titulo)}\s*\n([\s\S]*?)(?=\n##\s|$)', cuerpo, re.I)
        return m.group(1).strip() if m else False

    @classmethod
    def _parse_pasos(cls, cuerpo):
        sec = cls._seccion(cuerpo, 'Pasos')
        if not sec:
            return []
        pasos, actual = [], None
        inicio = re.compile(r'^\s*(?:\*\*)?(\d+)[.)](?:\*\*)?\s+(.*)$')
        for linea in sec.splitlines():
            m = inicio.match(linea)
            if m:
                if actual:
                    pasos.append(actual)
                actual = {'n': int(m.group(1)), 'texto': m.group(2)}
            elif actual and linea.strip():
                actual['texto'] += '\n' + linea.strip()
        if actual:
            pasos.append(actual)
        for p in pasos:
            img = re.search(r'`?\s*!\[[^\]]*\]\(([^)]+)\)\s*`?', p['texto'])
            if img:
                p['captura'] = img.group(1)
                p['texto'] = re.sub(r'[ \t]+', ' ', p['texto'].replace(img.group(0), '')).strip()
        return pasos


class FormacionAdjunto(models.Model):
    """Imagen referenciada dentro de las secciones de texto de una guía."""
    _name = 'formacion.adjunto'
    _description = 'Imagen de sección de una guía de formación'

    ficha_id = fields.Many2one('formacion.ficha', required=True, ondelete='cascade')
    nombre = fields.Char('Nombre de fichero', required=True, index=True)
    imagen = fields.Image('Imagen', max_width=1920, max_height=1920)


class FormacionTiempo(models.Model):
    """Horas de desarrollo invertidas en una guía (o en corregir un gap)."""
    _name = 'formacion.tiempo'
    _description = 'Horas de desarrollo de formación'
    _order = 'fecha desc'

    ficha_id = fields.Many2one('formacion.ficha', required=True, ondelete='cascade')
    gap_id = fields.Many2one('formacion.gap', string='Gap corregido', ondelete='set null',
                             domain="[('ficha_id', '=', ficha_id)]")
    usuario = fields.Char('Quién', default=lambda self: self.env.user.name, required=True)
    fecha = fields.Date(default=fields.Date.context_today, required=True)
    horas = fields.Float('Horas', required=True)
    descripcion = fields.Char('Qué se hizo')


class FormacionComentario(models.Model):
    """Comentario libre del cliente (no bloquea la validación, a diferencia del gap)."""
    _name = 'formacion.comentario'
    _description = 'Comentario del cliente sobre una guía'
    _order = 'fecha desc'

    ficha_id = fields.Many2one('formacion.ficha', required=True, ondelete='cascade')
    texto = fields.Text('Comentario', required=True)
    autor = fields.Char('Autor')
    login = fields.Char('Usuario (login)')
    fecha = fields.Datetime(default=fields.Datetime.now, required=True)
    origen = fields.Selection([('visor', 'Formador (Odoo)'), ('publico', 'Enlace público')],
                              default='visor')


class FormacionValidacion(models.Model):
    """Acta de aceptación del cliente. Inmutable: es la prueba de qué se validó y cuándo."""
    _name = 'formacion.validacion'
    _description = 'Acta de validación de una guía por el cliente'
    _order = 'fecha desc'

    ficha_id = fields.Many2one('formacion.ficha', required=True, ondelete='restrict')
    usuario = fields.Char('Validada por', required=True)
    login = fields.Char('Usuario (login)')
    fecha = fields.Datetime('Fecha', default=fields.Datetime.now, required=True)
    observacion = fields.Text('Observación del cliente')

    def write(self, vals):
        raise ValidationError('Las actas de validación no se modifican: son la prueba de la aceptación.')

    def unlink(self):
        raise ValidationError('Las actas de validación no se borran: son la prueba de la aceptación.')


class FormacionGap(models.Model):
    """Aviso del cliente: algo de la guía no cuadra con su Odoo real."""
    _name = 'formacion.gap'
    _description = 'Gap reportado sobre una guía de formación'
    _order = 'create_date desc'

    ficha_id = fields.Many2one('formacion.ficha', required=True, ondelete='cascade')
    area_id = fields.Many2one(related='ficha_id.area_id', store=True, string='Área')
    paso_n = fields.Integer('Paso nº', help='Paso concreto al que se refiere (0 = la guía en general)')
    descripcion = fields.Text('Qué no cuadra', required=True)
    reportado_por = fields.Char('Reportado por')
    estado = fields.Selection([('abierto', 'Abierto'),
                               ('corregido', 'Corregido'),
                               ('descartado', 'Descartado')],
                              default='abierto', required=True, group_expand='_expand_estados')
    respuesta = fields.Text('Nuestra respuesta / corrección')

    @api.depends('ficha_id.name', 'paso_n')
    def _compute_display_name(self):
        for gap in self:
            base = gap.ficha_id.name or 'Gap'
            gap.display_name = f'{base} — paso {gap.paso_n}' if gap.paso_n else base

    @api.model
    def _expand_estados(self, states, domain, order=None):
        return ['abierto', 'corregido', 'descartado']

    def write(self, vals):
        # El tablero del cliente promete explicación en Corregido / No procede: sin respuesta no se cierra
        if vals.get('estado') in ('corregido', 'descartado'):
            for gap in self:
                respuesta = vals['respuesta'] if 'respuesta' in vals else gap.respuesta
                if not (respuesta or '').strip():
                    raise ValidationError(
                        'Escribe "Nuestra respuesta" antes de marcarlo como corregido o no procede: '
                        'es la explicación que verá el cliente en su tablero de avisos.')
        return super().write(vals)


class FormacionPaso(models.Model):
    _name = 'formacion.paso'
    _description = 'Paso de una guía de formación'
    _order = 'ficha_id, sequence'

    ficha_id = fields.Many2one('formacion.ficha', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    n = fields.Integer('Nº', compute='_compute_n', store=True,
                       help='Número visible del paso — se calcula solo según el orden')
    texto = fields.Text('Qué hacer', required=True)
    captura = fields.Image('Captura', max_width=1920, max_height=1920,
                           help='La pantalla real con lo que hay que pulsar marcado')
    captura_nombre = fields.Char('Nombre del fichero')

    @api.depends('sequence', 'ficha_id', 'ficha_id.paso_ids', 'ficha_id.paso_ids.sequence')
    def _compute_n(self):
        for ficha in self.ficha_id:
            for i, paso in enumerate(ficha.paso_ids.sorted(lambda p: (p.sequence, p.id or 0)), start=1):
                paso.n = i
        for paso in self.filtered(lambda p: not p.ficha_id):
            paso.n = 0
