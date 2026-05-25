def migrate(cr, version):
    # Limpiar back-orders existentes que heredaron qty_validated/qty_ready_to_validate
    # de su madre antes del fix copy=False.
    cr.execute('''
        UPDATE mrp_workorder wo
        SET qty_validated = 0, qty_ready_to_validate = 0
        FROM mrp_production mp
        WHERE wo.production_id = mp.id
          AND mp.backorder_sequence > 0
          AND mp.state != 'done'
    ''')
