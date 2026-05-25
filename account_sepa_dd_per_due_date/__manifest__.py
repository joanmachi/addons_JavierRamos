# -*- coding: utf-8 -*-
{
    'name': 'SEPA DD - Cobro por fecha de vencimiento de factura',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Un PmtInf por fecha de vencimiento en el PAIN.008 SEPA DD.',
    'author': 'Personalización',
    'depends': [
        'account_sepa_direct_debit',
        'account_batch_payment',
    ],
    'data': [],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}