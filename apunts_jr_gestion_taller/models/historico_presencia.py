from odoo import fields, models, tools


class ApuntsHistoricoPresencia(models.Model):
    """Vista SQL de solo lectura que une PRESENCIAS (hr.attendance) y AUSENCIAS
    aprobadas (hr.leave) en una sola lista filtrable. No almacena datos: refleja
    en vivo ambos modelos. El id es estable y único:
      · presencia  = attendance.id * 10
      · ausencia   = leave.id * 10 + 1
    """
    _name = 'apunts.historico.presencia'
    _description = 'Histórico de presencia (presencias + ausencias)'
    _auto = False
    _order = 'fecha desc, employee_id'

    employee_id  = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    department_id = fields.Many2one('hr.department', string='Departamento', readonly=True)
    fecha        = fields.Date(string='Fecha', readonly=True)
    tipo         = fields.Selection([
        ('presencia', 'Presencia'),
        ('ausencia', 'Ausencia'),
    ], string='Tipo', readonly=True)
    hora_inicio  = fields.Datetime(string='Inicio', readonly=True)
    hora_fin     = fields.Datetime(string='Fin', readonly=True)
    horas        = fields.Float(string='Horas', readonly=True, digits=(16, 2))
    detalle      = fields.Char(string='Detalle', readonly=True)

    def action_open_record(self):
        """Abre el registro ORIGINAL de esta fila: la asistencia (hr.attendance)
        si es presencia, o la ausencia (hr.leave) si es ausencia. El id de la
        vista codifica el origen: original = id // 10, tipo = id % 10."""
        self.ensure_one()
        if self.tipo == 'presencia':
            res_model, name = 'hr.attendance', 'Asistencia'
        else:
            res_model, name = 'hr.leave', 'Ausencia'
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'res_id': self.id // 10,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                SELECT
                    a.id * 10                AS id,
                    a.employee_id            AS employee_id,
                    e.department_id          AS department_id,
                    (a.check_in)::date       AS fecha,
                    'presencia'              AS tipo,
                    a.check_in               AS hora_inicio,
                    a.check_out              AS hora_fin,
                    a.worked_hours           AS horas,
                    NULL::varchar            AS detalle
                FROM hr_attendance a
                JOIN hr_employee e ON e.id = a.employee_id

                UNION ALL

                SELECT
                    l.id * 10 + 1            AS id,
                    l.employee_id            AS employee_id,
                    e.department_id          AS department_id,
                    (l.date_from)::date      AS fecha,
                    'ausencia'               AS tipo,
                    l.date_from              AS hora_inicio,
                    l.date_to                AS hora_fin,
                    l.number_of_hours        AS horas,
                    COALESCE(lt.name->>'es_ES', lt.name->>'en_US') AS detalle
                FROM hr_leave l
                JOIN hr_employee e ON e.id = l.employee_id
                LEFT JOIN hr_leave_type lt ON lt.id = l.holiday_status_id
                WHERE l.state = 'validate'
            )
        """ % (self._table,))
