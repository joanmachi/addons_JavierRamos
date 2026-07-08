import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApuntsTallerDesbloqueo(models.Model):
    """Histórico de desbloqueos de operarios (trazabilidad).

    Se crea un registro AUTOMÁTICAMENTE cada vez que un empleado pasa de
    bloqueado → desbloqueado, venga del wizard "Corregir fichaje /
    desbloquear" o de quitar el check a mano en la ficha. No se pide nada
    a nadie: es solo traza.

    Además del quién/cuándo, guarda una FOTO de los datos de jornada en el
    momento del desbloqueo (esperadas / presencia / ausencias del día de la
    incidencia). Si en ese momento los datos ya cumplían la jornada
    (`cumple_ahora`), el bloqueo se debió a datos que llegaron o se
    corrigieron tarde — esa es la traza de "por qué el programa falla".
    """

    _name = "apunts.taller.desbloqueo"
    _description = "Histórico de desbloqueos de operarios"
    _order = "fecha_desbloqueo desc, id desc"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Operario",
        required=True,
        index=True,
        readonly=True,
        ondelete="cascade",
    )
    tipo_bloqueo = fields.Selection(
        selection=[
            ("jornada", "Jornada insuficiente"),
            ("inactividad", "Inactividad (sin fichaje activo)"),
            ("fichaje_largo", "Fichaje continuo demasiado largo"),
            ("otro", "Otro"),
        ],
        string="Tipo de bloqueo",
        readonly=True,
        index=True,
    )
    motivo_bloqueo = fields.Char(
        string="Motivo del bloqueo (sistema)", readonly=True
    )
    fecha_bloqueo = fields.Datetime(string="Bloqueado el", readonly=True)
    dia_incidencia = fields.Date(
        string="Día de la incidencia",
        readonly=True,
        help="Día evaluado por el bloqueo (extraído del motivo). En jornada "
        "insuficiente es el día laborable anterior al bloqueo.",
    )
    fecha_desbloqueo = fields.Datetime(
        string="Desbloqueado el", readonly=True, default=fields.Datetime.now
    )
    desbloqueado_por_id = fields.Many2one(
        "res.users",
        string="Desbloqueado por",
        readonly=True,
        default=lambda self: self.env.user,
    )
    duracion_bloqueo_h = fields.Float(
        string="Horas bloqueado", readonly=True, digits=(16, 2)
    )

    con_correccion = fields.Boolean(
        string="Con OF",
        readonly=True,
        help="True si al desbloquear se corrigió o creó un fichaje en una OF. "
        "False = desbloqueo 'a pelo', sin OF ni corrección.",
    )
    production_id = fields.Many2one(
        "mrp.production", string="OF vinculada", readonly=True
    )
    motivo_correccion = fields.Char(
        string="Motivo de la corrección", readonly=True
    )
    ausencia_id = fields.Many2one(
        "hr.leave", string="Ausencia creada", readonly=True
    )
    accion = fields.Text(
        string="Acción realizada",
        readonly=True,
        help="Detalle de lo que se hizo al desbloquear (texto del wizard) o "
        "'Desbloqueo directo' si se quitó el check a mano.",
    )

    # Foto de los datos de jornada EN EL MOMENTO del desbloqueo
    horas_esperadas = fields.Float(
        string="Esperadas (h)", readonly=True, digits=(16, 2)
    )
    horas_presencia = fields.Float(
        string="Presencia (h)", readonly=True, digits=(16, 2)
    )
    horas_ausencia = fields.Float(
        string="Ausencia (h)", readonly=True, digits=(16, 2)
    )
    cumple_ahora = fields.Boolean(
        string="Cumple ahora",
        readonly=True,
        help="True si, con los datos que había AL DESBLOQUEAR, la jornada del "
        "día de la incidencia ya se daba por cumplida (presencia + ausencias "
        "≥ esperadas − tolerancia). Es la señal de que el bloqueo se debió a "
        "datos que llegaron o se corrigieron tarde, no a una falta real.",
    )

    @api.model
    def _crear_desde_desbloqueo(self, emp, motivo, fecha_bloqueo, info=None):
        """Crea la entrada del histórico. `motivo`/`fecha_bloqueo` son los
        valores del empleado ANTES de limpiarse; `info` es el dict opcional
        que pasa el wizard por contexto (acción, OF, motivo corrección...).
        Nunca lanza: la traza no puede romper un desbloqueo.
        """
        info = info or {}
        motivo = motivo or ""

        if "Jornada insuficiente" in motivo:
            tipo = "jornada"
        elif "sin fichaje activo" in motivo:
            tipo = "inactividad"
        elif "Fichaje continuo" in motivo:
            tipo = "fichaje_largo"
        else:
            tipo = "otro"

        dia = None
        m = re.search(r"(\d{4}-\d{2}-\d{2})", motivo)
        if m:
            dia = fields.Date.from_string(m.group(1))

        ahora = fields.Datetime.now()
        duracion = 0.0
        if fecha_bloqueo:
            duracion = (ahora - fecha_bloqueo).total_seconds() / 3600.0

        vals = {
            "employee_id": emp.id,
            "tipo_bloqueo": tipo,
            "motivo_bloqueo": motivo or False,
            "fecha_bloqueo": fecha_bloqueo or False,
            "dia_incidencia": dia,
            "fecha_desbloqueo": ahora,
            "desbloqueado_por_id": self.env.user.id,
            "duracion_bloqueo_h": round(duracion, 2),
            "con_correccion": bool(info.get("con_correccion")),
            "production_id": info.get("production_id") or False,
            "motivo_correccion": info.get("motivo_correccion") or False,
            "ausencia_id": info.get("ausencia_id") or False,
            "accion": info.get("accion") or "Desbloqueo directo (check quitado a mano, sin wizard).",
        }

        # Foto de jornada del día de la incidencia con los datos ACTUALES
        if tipo == "jornada" and dia:
            try:
                esperadas = emp._apunts_horas_esperadas(dia)
                pres = emp._apunts_horas_presencia(dia)
                aus = emp._apunts_horas_ausencia(dia)
                tolerancia_h = int(
                    self.env["ir.config_parameter"].sudo().get_param(
                        "apunts_taller_control.jornada_tolerancia_min", "10"
                    )
                ) / 60.0
                vals.update(
                    {
                        "horas_esperadas": round(esperadas, 2),
                        "horas_presencia": round(pres, 2),
                        "horas_ausencia": round(aus, 2),
                        "cumple_ahora": bool(
                            esperadas
                            and pres + aus >= esperadas - tolerancia_h
                        ),
                    }
                )
            except Exception as e:
                _logger.warning(
                    "Apunts: no se pudo calcular la foto de jornada del "
                    "desbloqueo de %s: %s",
                    emp.name,
                    e,
                )

        try:
            return self.sudo().create(vals)
        except Exception as e:
            _logger.error(
                "Apunts: fallo creando histórico de desbloqueo de %s: %s",
                emp.name,
                e,
            )
            return self.browse()


class HrEmployeeDesbloqueoLog(models.Model):
    _inherit = "hr.employee"

    def write(self, vals):
        # Trazar toda transición bloqueado → desbloqueado, venga del wizard
        # (que añade contexto apunts_desbloqueo_info) o de quitar el check a
        # mano en la ficha del empleado.
        antes = {}
        if "apunts_taller_bloqueado" in vals and not vals.get(
            "apunts_taller_bloqueado"
        ):
            for emp in self:
                if emp.apunts_taller_bloqueado:
                    antes[emp.id] = (
                        emp.apunts_taller_motivo_bloqueo,
                        emp.apunts_taller_fecha_bloqueo,
                    )
        res = super().write(vals)
        if antes:
            info = self.env.context.get("apunts_desbloqueo_info")
            Log = self.env["apunts.taller.desbloqueo"]
            for emp in self:
                if emp.id in antes:
                    motivo, fecha = antes[emp.id]
                    Log._crear_desde_desbloqueo(emp, motivo, fecha, info)
        return res
