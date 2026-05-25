# -*- coding: utf-8 -*-
"""
account_sepa_dd_per_due_date — Odoo 18 Enterprise
==================================================
Sobrescribe _generate_export_file de account_sepa_direct_debit (Enterprise).

El Enterprise devuelve un dict {'filename': str, 'file': bytes_base64}.
Interceptamos ese dict, reorganizamos el PAIN.008 y lo devolvemos corregido.
"""

import base64
import logging
from collections import defaultdict
from copy import deepcopy

from lxml import etree

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PAIN_NS = 'urn:iso:std:iso:20022:tech:xsd:pain.008.001.02'
INVOICE_TYPES = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
RECEIVABLE_TYPES = ('asset_receivable', 'liability_payable')


def _tag(local):
    return f'{{{PAIN_NS}}}{local}'


class AccountBatchPaymentSepaPerDate(models.Model):
    _inherit = 'account.batch.payment'

    # ------------------------------------------------------------------
    # Override principal — intercepta el dict que devuelve Enterprise
    # ------------------------------------------------------------------

    def _generate_export_file(self):
        """
        El Enterprise devuelve {'filename': '...xml', 'file': <bytes base64>}.
        Llamamos a super(), decodificamos el XML, lo reorganizamos por fecha
        de vencimiento y devolvemos el dict modificado.
        """
        _logger.warning('SEPA PER DATE [_generate_export_file] — inicio, lote: %s', self.name)

        result = super()._generate_export_file()

        _logger.warning('SEPA PER DATE [_generate_export_file] — resultado super() tipo: %s', type(result))

        # Verificar que es SEPA DD y que el resultado es el dict de Enterprise
        sdd_codes = self.payment_method_id._get_sdd_payment_method_code()
        if self.payment_method_code not in sdd_codes:
            return result

        if not isinstance(result, dict) or 'file' not in result:
            _logger.warning('SEPA PER DATE — resultado inesperado (no es dict): %s', result)
            return result

        try:
            # Decodificar el XML del campo 'file'
            raw_file = result['file']
            xml_bytes = base64.decodebytes(
                raw_file if isinstance(raw_file, bytes) else raw_file.encode()
            )

            if PAIN_NS.encode() not in xml_bytes:
                _logger.warning('SEPA PER DATE — no es PAIN.008, se devuelve sin modificar')
                return result

            # Construir mapa de fechas de vencimiento
            due_date_map = self._build_due_date_map()
            _logger.warning('SEPA PER DATE — mapa fechas: %s', {k: str(v) for k, v in due_date_map.items()})

            # Reorganizar el XML
            modified_bytes = self._regroup_pain008_by_date(xml_bytes, due_date_map)

            _logger.warning('SEPA PER DATE — XML reorganizado correctamente')
            return {
                **result,
                'file': base64.encodebytes(modified_bytes),
            }

        except Exception as e:
            _logger.error('SEPA PER DATE — error: %s', e, exc_info=True)
            return result

    # ------------------------------------------------------------------
    # Botón manual (acción de servidor definida en el XML de vistas)
    # ------------------------------------------------------------------

    def action_adjust_sepa_dates(self):
        """Acción manual: lee el export_file actual y lo reorganiza."""
        self.ensure_one()
        _logger.warning('SEPA PER DATE [botón] — lote: %s', self.name)

        if not self.export_file:
            raise UserError(_('Genera primero el fichero con "Validate".'))

        xml_bytes = base64.decodebytes(self.export_file)
        if PAIN_NS.encode() not in xml_bytes:
            raise UserError(_('El fichero no parece un PAIN.008 SEPA válido.'))

        due_date_map = self._build_due_date_map()
        _logger.warning('SEPA PER DATE [botón] — mapa: %s', {k: str(v) for k, v in due_date_map.items()})

        modified = self._regroup_pain008_by_date(xml_bytes, due_date_map)
        self.export_file = base64.encodebytes(modified)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fechas ajustadas'),
                'message': _('El fichero SEPA se ha reorganizado con las fechas de vencimiento.'),
                'type': 'success',
            },
        }

    # ------------------------------------------------------------------
    # Mapa EndToEndId → fecha de vencimiento
    # ------------------------------------------------------------------

    def _build_due_date_map(self):
        return {p.name: self._get_due_date_for_payment(p) for p in self.payment_ids}

    def _get_due_date_for_payment(self, payment):
        # 1. reconciled_invoice_ids
        try:
            dates = [inv.invoice_date_due for inv in payment.reconciled_invoice_ids if inv.invoice_date_due]
            if dates:
                return max(dates)
        except Exception:
            pass

        # 2. date_maturity en líneas del asiento
        try:
            lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in RECEIVABLE_TYPES and l.date_maturity
            )
            if lines:
                return max(lines.mapped('date_maturity'))
        except Exception:
            pass

        # 3. matched_debit/credit_ids
        try:
            recv = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in RECEIVABLE_TYPES
            )
            dates = []
            for line in recv:
                for p in line.matched_debit_ids:
                    mv = p.debit_move_id.move_id
                    if mv.move_type in INVOICE_TYPES and mv.invoice_date_due:
                        dates.append(mv.invoice_date_due)
                for p in line.matched_credit_ids:
                    mv = p.credit_move_id.move_id
                    if mv.move_type in INVOICE_TYPES and mv.invoice_date_due:
                        dates.append(mv.invoice_date_due)
            if dates:
                return max(dates)
        except Exception:
            pass

        # 4. Buscar factura por referencia
        try:
            ref = payment.ref or getattr(payment, 'memo', '') or ''
            if ref:
                inv = self.env['account.move'].search(
                    [('name', '=', ref), ('move_type', 'in', INVOICE_TYPES), ('invoice_date_due', '!=', False)],
                    limit=1,
                ) or self.env['account.move'].search(
                    [('ref', '=', ref), ('move_type', 'in', INVOICE_TYPES), ('invoice_date_due', '!=', False)],
                    limit=1,
                )
                if inv:
                    return inv.invoice_date_due
        except Exception:
            pass

        _logger.warning('SEPA PER DATE — fallback a payment.date para %s', payment.name)
        return payment.date

    # ------------------------------------------------------------------
    # Reorganización del XML
    # ------------------------------------------------------------------

    def _regroup_pain008_by_date(self, xml_bytes, due_date_map):
        doc = etree.fromstring(xml_bytes)
        initn = doc.find(_tag('CstmrDrctDbtInitn'))
        pmt_infs = initn.findall(_tag('PmtInf'))
        if not pmt_infs:
            return xml_bytes

        transactions = []
        for pi in pmt_infs:
            for tx in pi.findall(_tag('DrctDbtTxInf')):
                e2e = tx.findtext(f'{_tag("PmtId")}/{_tag("EndToEndId")}') or ''
                date = due_date_map.get(e2e) or pi.findtext(_tag('ReqdColltnDt'))
                transactions.append((str(date), deepcopy(tx), pi))

        for pi in pmt_infs:
            initn.remove(pi)

        by_date = defaultdict(list)
        for date_str, tx_elem, src_pi in transactions:
            by_date[date_str].append((tx_elem, src_pi))

        _logger.warning('SEPA PER DATE — %d PmtInf: %s', len(by_date), sorted(by_date.keys()))

        for idx, col_date in enumerate(sorted(by_date.keys())):
            tx_list = by_date[col_date]
            template_pi = tx_list[0][1]
            new_pi = etree.SubElement(initn, _tag('PmtInf'))
            for child in template_pi:
                local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local != 'DrctDbtTxInf':
                    new_pi.append(deepcopy(child))
            self._set_xml_text(new_pi, 'PmtInfId', f'{self.id}.{col_date.replace("-","")}/{idx}')
            self._set_xml_text(new_pi, 'NbOfTxs', str(len(tx_list)))
            self._set_xml_text(new_pi, 'CtrlSum', f'{self._sum_amounts(tx_list):.2f}')
            self._set_xml_text(new_pi, 'ReqdColltnDt', col_date)
            for tx_elem, _ in tx_list:
                new_pi.append(tx_elem)

        return etree.tostring(doc, pretty_print=True, xml_declaration=True, encoding='utf-8')

    @staticmethod
    def _set_xml_text(parent, local_name, value):
        el = parent.find(_tag(local_name))
        if el is not None:
            el.text = value
        else:
            etree.SubElement(parent, _tag(local_name)).text = value

    @staticmethod
    def _sum_amounts(tx_list):
        total = 0.0
        for tx_elem, _ in tx_list:
            amt = tx_elem.find(_tag('InstdAmt'))
            if amt is not None:
                try:
                    total += float(amt.text)
                except (TypeError, ValueError):
                    pass
        return total