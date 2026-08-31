# -*- coding: utf-8 -*-
"""Asistente de importación de guías desde un ZIP — sin consola.

El ZIP puede ser el repo web original (contenido/fichas + public/capturas),
una exportación hecha desde aquí (botón "Exportar ZIP"), o cualquier carpeta
con .md e imágenes: los .md son guías y las imágenes se casan por nombre."""
import base64
import io
import zipfile

from odoo import fields, models
from odoo.exceptions import UserError

TAMANO_MAX_FICHERO = 40 * 1024 * 1024  # por fichero dentro del zip


class FormacionImportar(models.TransientModel):
    _name = 'formacion.importar'
    _description = 'Importar guías de formación desde un ZIP'

    fichero = fields.Binary('Fichero ZIP', required=True, attachment=False)
    nombre_fichero = fields.Char('Nombre del fichero')

    def action_importar(self):
        self.ensure_one()
        try:
            z = zipfile.ZipFile(io.BytesIO(base64.b64decode(self.fichero)))
        except (zipfile.BadZipFile, ValueError):
            raise UserError('Ese fichero no es un ZIP válido. Comprime la carpeta '
                            'de guías (.md + imágenes) y vuelve a intentarlo.')
        ficheros = {}
        for info in z.infolist():
            if info.is_dir() or info.file_size > TAMANO_MAX_FICHERO:
                continue
            ficheros[info.filename] = z.read(info)
        res = self.env['formacion.ficha']._importar_ficheros(ficheros)
        if not res['creadas'] and not res['actualizadas']:
            raise UserError('El ZIP no contiene ninguna guía (.md). Estructura esperada: '
                            'ficheros .md con su cabecera --- (id, titulo, area...) y las '
                            'imágenes referenciadas, en cualquier carpeta del ZIP.')
        mensaje = f"{res['creadas']} guía(s) creada(s), {res['actualizadas']} actualizada(s)."
        if res['avisos']:
            avisos = res['avisos'][:8]
            if len(res['avisos']) > 8:
                avisos.append(f"... y {len(res['avisos']) - 8} aviso(s) más")
            mensaje += '\n⚠️ ' + '\n⚠️ '.join(avisos)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': 'Importación terminada',
                'message': mensaje,
                'type': 'warning' if res['avisos'] else 'success',
                'sticky': bool(res['avisos']),
                'next': {'type': 'ir.actions.act_window', 'name': 'Guías importadas',
                         'res_model': 'formacion.ficha', 'view_mode': 'list,form',
                         # `views` explícito: sin él, _preprocessAction de Odoo 18
                         # hace .map sobre undefined y peta ("Cannot read
                         # properties of undefined (reading 'map')"). La import
                         # sí se hace; solo fallaba abrir la lista al terminar.
                         'views': [[False, 'list'], [False, 'form']],
                         'domain': [('id', 'in', res['ids'])]},
            },
        }
