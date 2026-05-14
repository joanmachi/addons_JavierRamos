# -*- coding: utf-8 -*-
{
    'name': "Impuesto plastico",

    'summary': """
        Impuesto especial sobre los envases de plástico no reutilizables""",

    'description': """
        Impuesto especial sobre los envases de plástico no reutilizables
    """,

    'author': "Apunts informatica",
    'website': "https://www.apunts.es/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['sale', 'product', 'stock','account','l10n_es_aeat_mod592'],

    # always loaded
     'data': [
        'views/product.xml',
        
    ],
  
    'installable':True,
}
