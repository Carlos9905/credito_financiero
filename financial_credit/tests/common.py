from datetime import datetime
from odoo import fields
from odoo.tests import Form, tagged, common

@tagged('post_install', '-at_install')
class TestPayment(common.TransactionCase):
    """"
    Test del módelo de credito, asegura la eficiencia del código
    """

    @classmethod
    def setUpClass(cls):
        super(TestPayment, cls).setUpClass()
        
        cls.credit = cls.env["financial.credit"]

        cls.res_partner = cls.env["res.partner"]
        cls.product_id = cls.env["product.product"]
        cls.frecuencia_id = cls.env["frecuencia.credito"]
        cls.cuotas_id = cls.env["cuotas.credito"]
        cls.tipo_credito_id = cls.env["tipo.credito"]
        cls.lineas_credito = cls.env["lineas.credito"]

        cls.carlos = cls.res_partner.create(dict(name="Carlos", vat="BE0477472701", phone="56902351"))
        cls.martha = cls.res_partner.create(dict(name="Martha", vat="BE0477472702", phone="55985397"))
        
        cls.interes_producto = cls.product_id.create(dict(name="Interés", list_price=1.0, standard_price=1.0, default_code="INT_CF", type="service"))
        cls.financiamiento_producto = cls.product_id.create(dict(name="Financiamiento", list_price=1.0, standard_price=1.0, default_code="SER_CF", type="service"))

        cls.cuota3 = cls.cuotas_id.create(dict(nombre="x_Cuota 3", numero=3))
        cls.cuota6 = cls.cuotas_id.create(dict(nombre="Cuota 6", numero=6))

        cls.interes_1_35 = cls.tipo_credito_id.create(dict(name="x_Intres 1.35%", interes=0.013500000000000002, max_financiar=1))

        cls.frecuencia_mensual = cls.frecuencia_id.create(dict(nombre="x_Mensual", tipo_frecuencia="meses", cuotas_ids=[(6, 0, [cls.cuota3.id, cls.cuota6.id])]))

        # Create user.
        cls.user = cls.env['res.users'].create({
            'name': 'Because I am accountman!',
            'login': 'accountman',
            'password': 'accountman',
            'tz': 'America/Guatemala',
            'groups_id': [(6, 0, cls.env.user.groups_id.ids), (4, cls.env.ref('account.group_account_user').id)],
        })
        cls.user.partner_id.email = 'accountman@test.com'
        cls.env = cls.env(user=cls.user)

        cls.currency_usd_id = cls.env.ref("base.USD").id
        cls.bank_journal_usd = cls.env['account.journal'].create({'name': 'Bank US', 'type': 'bank', 'code': 'BNK68', 'currency_id': cls.currency_usd_id})
        cls.account_usd = cls.bank_journal_usd.default_account_id
    
    def test_payment(self):
        """
        Test de creación de un credito financiero
        """
        Credit = self.credit.with_user(self.user)
        venta_credito = Form(Credit,view="financial_credit.view_financial_credit_form")
        venta_credito.producto_id = self.env.ref("financial_credit.servi_finan_product")
        venta_credito.monto = 6000.00
        venta_credito.telefono = "56902351"
        venta_credito.cliente_id = self.res_partner.search([('name','=','Carlos')])
        venta_credito.tipo_amortiazacion = "lineal"
        venta_credito.frecuencia_pago = self.frecuencia_id.search([('nombre','=','x_Mensual')])
        venta_credito.cuota_id = self.cuotas_id.search([('nombre','=','x_Cuota 3')])
        venta_credito.fecha_primer_pago = datetime.strptime("24/05/2023", "%d/%m/%Y")
        venta_credito.tipo_credito_id = self.tipo_credito_id.search([("name", "=", "x_Intres 1.35%")])
        
        self.assertEqual(venta_credito.max_financiar, 1.0, msg="Max Financiamiento Incorrecto")
        self.assertEqual(venta_credito.monto_minimo_obli, 0.0, msg="Monto Minimo obligatorio incorrecto")

        venta_credito.monto_inicial = 0.0
        venta_credito.journals_id = self.env["account.journal"].search([("name", "=", "Bank US")])
        
        record_venta_credito = venta_credito.save()
        record_venta_credito.action_generate_table()

        self.assertEqual(record_venta_credito.precio, 6000.0, msg="Precio incorrecto")
        self.assertEqual(record_venta_credito.interes_mensual * 100, 1.35)
        self.assertEqual(record_venta_credito.total, 6000, msg="Total incorrecto")
        self.assertEqual(round(record_venta_credito.total_interes, 2), 243.00, msg="Total Interes incorrecto")
        self.assertEqual(round(record_venta_credito.deuda_total, 2), 6243.00, msg="Deuda Total incorrecto")
        self.assertEqual(round(record_venta_credito.cuota_fija, 2), 2081.00, msg="Cuota Fija incorrecto")
        self.assertEqual(record_venta_credito.state, "borrador", msg="Estado incorrecto")

        lineas_pagos = self.lineas_credito.search([("credito_id", "=", record_venta_credito.id)])
        ultima_linea = lineas_pagos.filtered(lambda x: x.numero == 3)
        self.assertEqual(len(lineas_pagos), 3)
        self.assertEqual(ultima_linea.cuota_inicial, 0.0, msg="Capital vivo incorrecto")
        self.assertEqual(ultima_linea.capital, 2000.0, msg="Capital incorrecto")
        self.assertEqual(ultima_linea.interes, 81.0, msg="Interes incorrecto")
        self.assertEqual(ultima_linea.fecha_pago.strftime("%d/%m/%Y"), "24/07/2023", msg="Fecha Pago incorrecto")