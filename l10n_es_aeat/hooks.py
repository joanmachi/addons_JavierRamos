# Copyright 2022 Acsone SA - Xavier Bouquiaux
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo import tools
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def create_column_thirdparty_invoice(cr):
    if not column_exists(
        cr, "account_journal", "thirdparty_invoice"
    ) and not column_exists(cr, "account_move", "thirdparty_invoice"):
        _logger.info("Initializing column thirdparty_invoice on table account_move")
        cr.execute(
            """
            ALTER TABLE account_move ADD COLUMN thirdparty_invoice boolean;
            COMMENT ON COLUMN account_move.thirdparty_invoice IS 'Third-party invoice' ;
            """
        )
        cr.execute(
            """
            ALTER TABLE account_journal ADD COLUMN thirdparty_invoice boolean;
            COMMENT ON COLUMN account_journal.thirdparty_invoice IS 'Third-party invoice' ;
            """
        )
   
   
        cr.execute("UPDATE account_move SET thirdparty_invoice = False")
        cr.execute("UPDATE account_journal SET thirdparty_invoice = False")


def pre_init_hook(env):
    create_column_thirdparty_invoice(env.cr)
