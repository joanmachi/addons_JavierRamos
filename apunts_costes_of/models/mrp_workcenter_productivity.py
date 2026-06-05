import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivityApunts(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    def _apunts_find_affected_productions(self):
        """Returns productions OTHER than self's own that have closed
        productivity records for the same employee overlapping self's
        time range. These need their labor lines regenerated so that
        the proration stays correct after this record is created/updated."""
        cr = self.env.cr
        affected = self.env['mrp.production']
        closed = self.filtered(lambda r: r.employee_id and r.date_start and r.date_end)
        for rec in closed:
            own_prod_id = (
                rec.workorder_id.production_id.id
                if rec.workorder_id and rec.workorder_id.production_id
                else 0
            )
            cr.execute("""
                SELECT DISTINCT wo.production_id
                FROM   mrp_workcenter_productivity p
                JOIN   mrp_workorder wo ON wo.id = p.workorder_id
                WHERE  p.employee_id = %s
                  AND  p.date_end IS NOT NULL
                  AND  p.date_start < %s
                  AND  p.date_end   > %s
                  AND  wo.production_id != %s
                  AND  p.id != %s
            """, [rec.employee_id.id, rec.date_end, rec.date_start,
                  own_prod_id, rec.id])
            prod_ids = [r[0] for r in cr.fetchall()]
            if prod_ids:
                affected |= self.env['mrp.production'].browse(prod_ids)
        return affected

    def _apunts_refresh_affected(self, affected):
        """Regenera líneas y dispara refresco de formulario para las producciones afectadas."""
        now = fields.Datetime.now()
        for prod in affected:
            prod._apunts_regenerate_lines()
        if affected:
            # Escribir un campo store=True en OF1 → Odoo manda notificación bus →
            # el formulario abierto en el navegador se refresca automáticamente.
            affected.write({'apunts_productivity_trigger': now})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        affected = records._apunts_find_affected_productions()
        self._apunts_refresh_affected(affected)
        return records

    def write(self, vals):
        keys_changed = [k for k in ('employee_id', 'date_start', 'date_end') if k in vals]
        pre_affected = self._apunts_find_affected_productions() if keys_changed else self.env['mrp.production']
        result = super().write(vals)
        if keys_changed:
            post_affected = self._apunts_find_affected_productions()
            affected = pre_affected | post_affected
            _logger.info('APUNTS hook write ids=%s keys=%s affected=%s',
                         self.ids, keys_changed, affected.ids)
            self._apunts_refresh_affected(affected)
        return result
