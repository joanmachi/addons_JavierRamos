import logging
from datetime import timedelta

import pytz

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class TallerControl(models.Model):
    _name = "apunts.taller.control"
    _description = "Crons de control de taller"

    @api.model
    def cron_alertar_fichajes_largos(self):
        """Punto 8 — fichajes abiertos > 16 horas."""
        limite = fields.Datetime.now() - timedelta(hours=16)
        productivities = self.env["mrp.workcenter.productivity"].search(
            [
                ("date_end", "=", False),
                ("date_start", "<", limite),
                ("employee_id", "!=", False),
            ]
        )
        for prod in productivities:
            target = prod.production_id or prod.workorder_id.production_id
            if not target:
                continue
            target.message_post(
                body=_(
                    "ALERTA fichaje anormal: el empleado %(emp)s lleva más "
                    "de 16 horas fichado en la orden de trabajo "
                    "%(wo)s (desde %(start)s)."
                )
                % {
                    "emp": prod.employee_id.name,
                    "wo": (prod.workorder_id.name or "?"),
                    "start": fields.Datetime.to_string(prod.date_start),
                },
                subject=_("Apunts: fichaje >16h"),
            )

    @api.model
    def cron_bloquear_fichajes_largos(self):
        """Punto 3 — bloquear empleado con fichaje continuo > N horas (configurable)."""
        ICP = self.env["ir.config_parameter"].sudo()
        horas = int(
            ICP.get_param("apunts_taller_control.bloqueo_horas_continuas_of", "12")
        )
        if not horas:
            return
        limite = fields.Datetime.now() - timedelta(hours=horas)
        productivities = self.env["mrp.workcenter.productivity"].search(
            [
                ("date_end", "=", False),
                ("date_start", "<", limite),
                ("employee_id", "!=", False),
            ]
        )
        bloqueados_ids = set()
        for prod in productivities:
            emp = prod.employee_id
            if not emp or emp.apunts_taller_bloqueado:
                continue
            if emp.id in bloqueados_ids:
                continue
            emp.write(
                {
                    "apunts_taller_bloqueado": True,
                    "apunts_taller_motivo_bloqueo": _(
                        "Fichaje continuo > %sh en orden %s"
                    )
                    % (horas, prod.workorder_id.name or "?"),
                    "apunts_taller_fecha_bloqueo": fields.Datetime.now(),
                }
            )
            bloqueados_ids.add(emp.id)

    @api.model
    def cron_bloquear_inactividad(self):
        """Punto 4 — bloquear empleado checked_in que lleva > N min sin
        fichaje activo en ninguna orden (configurable)."""
        ICP = self.env["ir.config_parameter"].sudo()
        minutos = int(
            ICP.get_param("apunts_taller_control.bloqueo_inactividad_min", "30")
        )
        if not minutos:
            return
        limite = fields.Datetime.now() - timedelta(minutes=minutos)
        attendances = self.env["hr.attendance"].search(
            [("check_out", "=", False)]
        )
        for att in attendances:
            emp = att.employee_id
            if not emp or emp.apunts_taller_bloqueado:
                continue
            tiene_abierta = self.env["mrp.workcenter.productivity"].search_count(
                [
                    ("date_end", "=", False),
                    ("employee_id", "=", emp.id),
                ]
            )
            if tiene_abierta:
                continue
            ultima = self.env["mrp.workcenter.productivity"].search(
                [
                    ("employee_id", "=", emp.id),
                    ("date_end", "!=", False),
                ],
                order="date_end DESC",
                limit=1,
            )
            referencia = ultima.date_end if ultima else att.check_in
            if not referencia or referencia >= limite:
                continue
            emp.write(
                {
                    "apunts_taller_bloqueado": True,
                    "apunts_taller_motivo_bloqueo": _(
                        "Más de %d minutos sin fichaje activo en ninguna orden"
                    )
                    % minutos,
                    "apunts_taller_fecha_bloqueo": fields.Datetime.now(),
                }
            )

    @api.model
    def _apunts_cerrar_asistencia_colgada(self, att):
        """Cierra una entrada que se quedó sin salida de un día anterior.

        La hora de salida es el momento en que el operario se desfichó del todo
        ese día: el último fichaje de OF que cerró. Si aquel día no llegó a
        fichar en ninguna orden, se usa la hora de salida de su calendario.
        Devuelve la hora aplicada, o False si no se pudo cerrar."""
        emp = att.employee_id
        if not emp or not att.check_in or att.check_out:
            return False
        # Día natural del operario (su hora local), no el día UTC
        dia = fields.Date.to_date(
            self._apunts_dt_local(att.check_in, emp).date()
        )
        ini, fin = emp._apunts_rango_utc(dia)
        # El último desfichaje de OF de ese día POSTERIOR a la entrada: es el
        # momento en que el operario se desfichó del todo.
        ultimo = self.env["mrp.workcenter.productivity"].sudo().search(
            [
                ("employee_id", "=", emp.id),
                ("date_end", "!=", False),
                ("date_end", ">", att.check_in),
                ("date_end", "<=", fin),
            ],
            order="date_end DESC",
            limit=1,
        )
        if ultimo:
            salida = ultimo.date_end
            nota = _(
                "Entrada del %(entrada)s cerrada automáticamente a las %(salida)s: "
                "el operario no fichó la salida, así que se ha usado el momento en "
                "que se desfichó de la última orden."
            ) % {"entrada": att.check_in, "salida": ultimo.date_end}
        else:
            # No hay ningún rastro de trabajo después de la entrada: no se
            # inventan horas de presencia. Se cierra en seco y se avisa para
            # que oficina ponga la hora buena a mano.
            salida = att.check_in + timedelta(minutes=1)
            nota = _(
                "Entrada del %(entrada)s cerrada automáticamente: el operario no "
                "fichó la salida y ese día no hay ningún fichaje de orden posterior, "
                "así que NO se puede saber a qué hora salió. Se ha cerrado sin horas: "
                "REVISAR y corregir la salida a mano si trabajó."
            ) % {"entrada": att.check_in}
        att.sudo().write({"check_out": salida})
        emp.sudo().message_post(body=nota)
        return salida

    @api.model
    def _apunts_dt_local(self, dt, emp):
        """Convierte un datetime UTC a la hora local del empleado."""
        tz = pytz.timezone(emp._get_tz() or "Europe/Madrid")
        return pytz.utc.localize(dt).astimezone(tz)

    @api.model
    def cron_bloquear_jornada_insuficiente(self):
        """Bloqueo 3 — jornada del día laborable anterior insuficiente.

        Criterio (acordado con cliente): cuenta la PRESENCIA (hr.attendance) +
        las AUSENCIAS aprobadas (hr.leave), igual que vería una inspección. Si
        ese total no alcanza la jornada teórica del calendario del empleado
        (descontando la tolerancia configurada), se bloquea. Solo se evalúan
        días laborables L-V sin festivos (ver helpers en hr.employee)."""
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("apunts_taller_control.bloqueo_jornada_activo", "1") != "1":
            return
        tolerancia_h = int(
            ICP.get_param("apunts_taller_control.jornada_tolerancia_min", "10")
        ) / 60.0

        # "Ayer" natural; el cron corre a diario, así findes/festivos se
        # descartan vía _apunts_horas_esperadas (devuelve 0 ⇒ se saltan).
        dia = fields.Date.context_today(self) - timedelta(days=1)

        empleados = self.env["hr.employee"].search(
            [("active", "=", True), ("resource_calendar_id", "!=", False)]
        )
        for emp in empleados:
            if emp.apunts_taller_bloqueado:
                continue
            esperadas = emp._apunts_horas_esperadas(dia)
            if not esperadas:
                continue  # finde / festivo para este empleado
            pres = emp._apunts_horas_presencia(dia)
            aus = emp._apunts_horas_ausencia(dia)
            if pres + aus < esperadas - tolerancia_h:
                emp.write(
                    {
                        "apunts_taller_bloqueado": True,
                        "apunts_taller_motivo_bloqueo": _(
                            "Jornada insuficiente el %(dia)s: %(pres).2f h "
                            "presencia + %(aus).2f h ausencia = %(tot).2f h "
                            "(esperadas %(esp).2f h)"
                        )
                        % {
                            "dia": fields.Date.to_string(dia),
                            "pres": pres,
                            "aus": aus,
                            "tot": pres + aus,
                            "esp": esperadas,
                        },
                        "apunts_taller_fecha_bloqueo": fields.Datetime.now(),
                    }
                )
