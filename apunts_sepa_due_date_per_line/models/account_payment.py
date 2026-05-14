import time
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr
from odoo.tools.xml_utils import create_xml_node
from lxml import etree


class AccountPayment(models.Model):
    _inherit = "account.payment"

    apunts_sdd_collection_date = fields.Date(
        string="Fecha cobro",
        compute="_compute_apunts_sdd_collection_date",
        store=True,
        readonly=False,
        help=(
            "Fecha de cobro SEPA para este pago concreto. Por defecto se "
            "rellena con la fecha de vencimiento de la factura asociada. "
            "Editable manualmente. Al generar el XML SEPA del batch, los "
            "pagos se agrupan por esta fecha — los que comparten fecha van "
            "en el mismo bloque PmtInf."
        ),
    )

    @api.depends("reconciled_invoice_ids", "reconciled_invoice_ids.invoice_date_due", "date")
    def _compute_apunts_sdd_collection_date(self):
        for pay in self:
            if pay.apunts_sdd_collection_date:
                # Si el usuario ya lo editó manualmente, no lo pisamos.
                continue
            due = False
            if pay.reconciled_invoice_ids:
                # Tomar la fecha de vencimiento más temprana de las facturas
                # reconciliadas. Si hay varias, la primera por vencimiento.
                due_dates = pay.reconciled_invoice_ids.mapped("invoice_date_due")
                due_dates = [d for d in due_dates if d]
                if due_dates:
                    due = min(due_dates)
            pay.apunts_sdd_collection_date = due or pay.date

    # ------------------------------------------------------------------
    # Generación XML SEPA — override completo de generate_xml para que
    # agrupe por (journal, apunts_sdd_collection_date) en vez de solo journal.
    # ------------------------------------------------------------------
    def generate_xml(self, company_id, required_collection_date, askBatchBooking):
        """Override: si los pagos del recordset tienen fechas distintas en
        `apunts_sdd_collection_date`, generamos un bloque PmtInf por cada
        fecha. Si todos comparten fecha (caso compatible con nativo),
        delegamos al super().
        """
        # Comprobar si hay fechas distintas
        fechas = set(
            pay.apunts_sdd_collection_date or required_collection_date
            for pay in self
        )
        if len(fechas) <= 1:
            return super().generate_xml(
                company_id, required_collection_date, askBatchBooking
            )

        version = self.journal_id.debit_sepa_pain_version
        if not version:
            raise UserError(
                _("Select a SEPA Direct Debit version before generating the XML.")
            )
        document = etree.Element(
            "Document",
            nsmap={
                None: f"urn:iso:std:iso:20022:tech:xsd:{version}",
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            },
        )
        CstmrDrctDbtInitn = etree.SubElement(document, "CstmrDrctDbtInitn")
        self._sdd_xml_gen_header(company_id, CstmrDrctDbtInitn)

        # Agrupar por (journal, fecha_cobro)
        payments_per_journal = self._group_payments_per_bank_journal()
        payment_info_counter = 0
        for journal, journal_payments in payments_per_journal.items():
            for fecha, fecha_payments in journal_payments._apunts_group_by_collection_date(
                fallback_date=required_collection_date
            ).items():
                fecha_payments._sdd_xml_gen_payment_group(
                    company_id,
                    fecha,
                    askBatchBooking,
                    payment_info_counter,
                    journal,
                    CstmrDrctDbtInitn,
                )
                payment_info_counter += 1

        return etree.tostring(
            document, pretty_print=True, xml_declaration=True, encoding="utf-8"
        )

    def _apunts_group_by_collection_date(self, fallback_date):
        """Agrupa el recordset por `apunts_sdd_collection_date` (o
        `fallback_date` si vacía). Devuelve dict {fecha: payments}.
        """
        grupos = {}
        for pay in self:
            fecha = pay.apunts_sdd_collection_date or fallback_date
            grupos.setdefault(fecha, self.browse())
            grupos[fecha] |= pay
        # Orden por fecha ascendente
        return dict(sorted(grupos.items()))


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    apunts_has_distinct_collection_dates = fields.Boolean(
        string="Fechas cobro distintas",
        compute="_compute_apunts_has_distinct_collection_dates",
        help=(
            "True si los pagos del lote tienen fechas de cobro distintas. "
            "En ese caso el XML SEPA tendrá múltiples bloques PmtInf."
        ),
    )

    @api.depends("payment_ids.apunts_sdd_collection_date")
    def _compute_apunts_has_distinct_collection_dates(self):
        for batch in self:
            fechas = set(batch.payment_ids.mapped("apunts_sdd_collection_date"))
            fechas.discard(False)
            batch.apunts_has_distinct_collection_dates = len(fechas) > 1
