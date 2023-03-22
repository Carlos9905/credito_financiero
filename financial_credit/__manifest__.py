# -*- coding: utf-8 -*-
{
    'name': 'Credito',
    'version': '15.0.2.0.0',
    'summary': """Modulo para gestionar financiamiento diversos.""",
    'description': """Modulo para gestionar financiamiento diversos.""",
    'author': 'Jose Aguilar',
    'company': 'BrainTech',
    'maintainer': 'BrainTech',
    'category': 'Credito',
    'website': 'https://braintech.odoobt.com',
    'license': 'LGPL-3', 
    'depends': ['base','product', 'account', 'sale_management'],
    'data': [
             'security/ir.model.access.csv',
             'security/aprobacion.xml',
             'data/data.xml',
             'data/fc_producto.xml',
             'report/report_view.xml',
             'report/ticket_report.xml',
             'views/boton_credito.xml',
             'views/credit_view_form.xml',
             'views/tipo_credito_tree.xml',
             'views/cuotas_view.xml',
             'views/res_partner_view.xml',
             'views/pagos_contable_view.xml',
             'views/reportes_view.xml',
             'views/frecuencia_view.xml',
             'views/payment_view_form.xml',
             'views/sale_order_view.xml',
             'views/res_config_settings_view_form.xml',
             'views/menu.xml',
             'wizard/wizard_reprogramar_cuotas.xml',
             ],
    'installable': True,
    'application': True,
}
