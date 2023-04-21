from datetime import datetime
from odoo import fields
from odoo.tests import Form, tagged, common
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

@tagged('post_install', '-at_install')
class TestCredit(common.TransactionCase):
    """"
    Test del módelo de credito, asegura la eficiencia del código
    """

    @classmethod
    def setUpClass(cls):
        super(TestCredit, cls).setUpClass()
        
        cls.credit = cls.env["financial.credit"]
        cls.payment = cls.env["payment.credit"]

        cls.res_partner = cls.env["res.partner"]
        cls.product_id = cls.env["product.product"]
        cls.frecuencia_id = cls.env["frecuencia.credito"]
        cls.cuotas_id = cls.env["cuotas.credito"]
        cls.tipo_credito_id = cls.env["tipo.credito"]
        cls.lineas_credito = cls.env["lineas.credito"]

        cls.carlos = cls.res_partner.create(dict(name="Carlos", vat="BE0477472701", phone="56902351"))
        cls.martha = cls.res_partner.create(dict(name="Martha", vat="BE0477472702", phone="55985397"))
        
        cls.financiamiento_producto = cls.product_id.create(dict(name="Financiamiento", list_price=1.0, standard_price=1.0, default_code="SER_CF", type="service"))

        cls.cuota3 = cls.cuotas_id.create(dict(nombre="x_Cuota 3", numero=3))
        cls.cuota6 = cls.cuotas_id.create(dict(nombre="Cuota 6", numero=6))

        cls.interes_1_35 = cls.tipo_credito_id.create(dict(name="x_Intres 1.35%", interes=0.013500000000000002, max_financiar=1))
        cls.interes_1_50 = cls.tipo_credito_id.create(dict(name="x_Intres 1.50%", interes=0.015, max_financiar=1))

        cls.frecuencia_mensual = cls.frecuencia_id.create(dict(nombre="x_Mensual", tipo_frecuencia="meses", cuotas_ids=[(6, 0, [cls.cuota3.id, cls.cuota6.id])]))

        # Create user.
        cls.user = cls.env['res.users'].create({
            'name': 'Because I am accountman!',
            'login': 'accountman',
            'password': 'accountman',
            'tz': 'America/Guatemala',
            'groups_id': [(6, 0, cls.env.user.groups_id.ids), (4, cls.env.ref('account.group_account_user').id),(4, cls.env.ref('financial_credit.view_aprobacion_field').id)],
        })
        cls.user.partner_id.email = 'accountman@test.com'
        cls.env = cls.env(user=cls.user)

        cls.currency_usd_id = cls.env.ref("base.GTQ").id
        cls.bank_journal_usd = cls.env['account.journal'].create({'name': 'Bank GTQ', 'type': 'bank', 'code': 'BNK68', 'currency_id': cls.currency_usd_id})
        cls.account_usd = cls.bank_journal_usd.default_account_id
        
    def objectOdooTolist(self,object):
        dic = []
        for item in object:
            dic.append(dict(numero=item.numero,
                            contacto=item.contacto.id,cuota_inicial=item.cuota_inicial,
                            cuota_fija=item.cuota_fija,interes=item.interes,capital=item.capital,
                            fecha_pago=item.fecha_pago,deuda_acum=item.deuda_acum,capital_acum=item.capital_acum,
                            interes_acum=item.interes_acum,payment_state=item.payment_state,
                            payment_date=item.payment_date,payment_amount=item.payment_amount,
                            mora=item.mora,credito_id=item.credito_id.id,paymet_id=item.paymet_id.id,currency_id=item.currency_id.id))
        return dic

    def test_crear_credito_lineal_1(self):
        """
        Test de creación de un credito financiero
        """
        _logger.log(logging.INFO, "Test1 Crear Credito Lineal")
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
        venta_credito.journals_id = self.env["account.journal"].search([("name", "=", "Bank GTQ")])
        
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
    
    def test_crear_credito_lineal_2(self):
        """
        Test de creación de un credito financiero Con pagos
        """
        _logger.log(logging.INFO, "Test1 Crear Credito Lineal Con Pagos")
        Credit = self.credit.with_user(self.user)
        venta_credito = Form(Credit,view="financial_credit.view_financial_credit_form")
        venta_credito.producto_id = self.env.ref("financial_credit.servi_finan_product")
        venta_credito.monto = 50000
        venta_credito.telefono = "56902351"
        venta_credito.cliente_id = self.res_partner.search([('name','=','Carlos')])
        venta_credito.tipo_amortiazacion = "lineal"
        venta_credito.frecuencia_pago = self.frecuencia_id.search([('nombre','=','x_Mensual')])
        venta_credito.cuota_id = self.cuotas_id.search([('nombre','=','x_Cuota 3')])
        venta_credito.fecha_primer_pago = datetime.strptime("08/05/2023", "%d/%m/%Y")
        venta_credito.tipo_credito_id = self.tipo_credito_id.search([("name", "=", "x_Intres 1.50%")])
        
        self.assertEqual(venta_credito.max_financiar, 1.0, msg="Max Financiamiento Incorrecto")
        self.assertEqual(venta_credito.monto_minimo_obli, 0.0, msg="Monto Minimo obligatorio incorrecto")

        venta_credito.monto_inicial = 0.0
        venta_credito.journals_id = self.env["account.journal"].search([("name", "=", "Bank GTQ")])
        
        record_venta_credito = venta_credito.save()
        record_venta_credito.action_generate_table()

        self.assertEqual(record_venta_credito.precio, 50000.0, msg="Precio incorrecto")
        self.assertEqual(record_venta_credito.interes_mensual * 100, 1.50)
        self.assertEqual(record_venta_credito.total, 50000, msg="Total incorrecto")
        self.assertEqual(round(record_venta_credito.total_interes, 2), 2250.00, msg="Total Interes incorrecto")
        self.assertEqual(round(record_venta_credito.deuda_total, 2), 52250.00, msg="Deuda Total incorrecto")
        self.assertEqual(round(record_venta_credito.cuota_fija, 2), 17416.67, msg="Cuota Fija incorrecto")
        self.assertEqual(record_venta_credito.state, "borrador", msg="Estado incorrecto")

        lineas_pagos = self.lineas_credito.search([("credito_id", "=", record_venta_credito.id)])
        ultima_linea = lineas_pagos.filtered(lambda x: x.numero == 3)
        self.assertEqual(len(lineas_pagos), 3)
        self.assertEqual(ultima_linea.cuota_inicial, 0.0, msg="Capital vivo incorrecto")
        self.assertEqual(round(ultima_linea.capital, 2), 16666.67, msg="Capital incorrecto")
        self.assertEqual(ultima_linea.interes, 750.00, msg="Interes incorrecto")
        self.assertEqual(ultima_linea.fecha_pago.strftime("%d/%m/%Y"), "08/07/2023", msg="Fecha Pago incorrecto")

        self.credit.search([("id", "=", record_venta_credito.id)]).write({"state": "aprobado"})

        record_venta_credito.action_factura()
        self.assertEqual(record_venta_credito.numero_facturas, 2, msg="Facturas no creadas")
        
        ############################ Pago 1 ############################
        Payment1 = self.payment.with_user(self.user)
        payment_credito1 = Form(Payment1,view="financial_credit.view_payment_credit_form")
        payment_credito1.credit_id = self.credit.search([("id", "=", record_venta_credito.id)])
        payment_credito1.cliente_id = self.res_partner.search([('name','=','Carlos')])
        payment_credito1.telefono = "56902351"

        self.assertEqual(round(payment_credito1.cuota_fija,2), 17416.67, msg="Cuota Fija incorrecto")
        self.assertEqual(payment_credito1.balance, 52250.00, msg="Balance incorrecto")
        self.assertEqual(payment_credito1.deuda_actual, 17416.67, msg="Deuda Actual incorrecto")

        payment_credito1.flujo_pago = "normal"
        payment_credito1.journal_id = self.env["account.journal"].search([("name", "=", "Bank GTQ")])
        payment_credito1.ref = "8456151354"
        record_payment_credito1 = payment_credito1.save()
        
        self.assertRaises(UserError, record_payment_credito1.action_confirm)

        _logger.log(logging.INFO, "Test2 Registrando Pago 1")
        record_payment_credito1.monto = 17416.67
        record_payment_credito1.action_confirm()
        n = record_payment_credito1.number.split("-")
        self.assertEqual(n[0], "PAY", msg="El pago no fue validado correctamente")
        
        record_payment_credito1.registrar_pago()
        self.assertEqual(record_payment_credito1.state, "pagado", msg="El pago no fue registrado correctamente")

        pagos_realizados1 = self.lineas_credito.search([("credito_id", "=", record_venta_credito.id)])
        primera_linea1 = pagos_realizados1.filtered(lambda x: x.numero == 1)
        self.assertEqual(primera_linea1.payment_amount, 17416.67, msg="Pago No realizado correctamente")
        self.assertEqual(primera_linea1.payment_state, "pagado")
        self.assertEqual(primera_linea1.deuda_acum, 0.0, msg="Deuda Acumulada incorrecto")
        self.assertEqual(primera_linea1.interes_acum, 0.0, msg="Interes Acumulado incorrecto")
        self.assertEqual(primera_linea1.capital_acum, 0.0, msg="Capital Acumulado incorrecto")
        self.assertTrue(primera_linea1.payment_date, msg="Fecha Pago incorrecto")
        
        _logger.log(logging.INFO, "Test2 verificando pagos pendientes")
        self.assertEqual(record_venta_credito.numero_pagos, 2, msg="Pagos no registrados correctamente")
        
        ############################ Pago 2 ############################
        _logger.log(logging.INFO, "Test2 Creando otro pago")
        Payment2 = self.payment.with_user(self.user)
        payment_credito2 = Form(Payment2,view="financial_credit.view_payment_credit_form")
        payment_credito2.credit_id = self.credit.search([("id", "=", record_venta_credito.id)])
        payment_credito2.cliente_id = self.res_partner.search([('name','=','Carlos')])
        payment_credito2.telefono = "56902351"

        self.assertEqual(round(payment_credito2.cuota_fija,2), 17416.67, msg="Cuota Fija incorrecto")
        self.assertEqual(payment_credito2.balance, 34833.33, msg="Balance incorrecto")
        self.assertEqual(payment_credito2.deuda_actual, 17416.67, msg="Deuda Actual incorrecto")

        payment_credito2.flujo_pago = "normal"
        payment_credito2.journal_id = self.env["account.journal"].search([("name", "=", "Bank GTQ")])
        payment_credito2.ref = "8456151354"
        record_payment_credito2 = payment_credito2.save()
        
        self.assertRaises(UserError, record_payment_credito2.action_confirm)

        _logger.log(logging.INFO, "Test2 Registrando Pago 2")
        record_payment_credito2.monto = payment_credito2.balance
        record_payment_credito2.action_confirm()
        n = record_payment_credito2.number.split("-")
        self.assertEqual(n[0], "PAY", msg="El pago no fue validado correctamente")
        
        record_payment_credito2.registrar_pago()
        self.assertEqual(record_payment_credito2.state, "pagado", msg="El pago no fue registrado correctamente")

        pagos_realizados2 = self.lineas_credito.search([("credito_id", "=", record_venta_credito.id)])
        primera_linea2 = pagos_realizados2.filtered(lambda x: x.numero == 2)
        self.assertEqual(primera_linea2.payment_amount, 17416.67, msg="Pago No realizado correctamente")
        self.assertEqual(primera_linea2.payment_state, "pagado")
        self.assertEqual(primera_linea2.deuda_acum, 0.0, msg="Deuda Acumulada incorrecto")
        self.assertEqual(primera_linea2.interes_acum, 0.0, msg="Interes Acumulado incorrecto")
        self.assertEqual(primera_linea2.capital_acum, 0.0, msg="Capital Acumulado incorrecto")
        self.assertTrue(primera_linea2.payment_date, msg="Fecha Pago incorrecto")
        
        primera_linea3 = pagos_realizados2.filtered(lambda x: x.numero == 3)
        self.assertEqual(primera_linea3.payment_amount, 17416.67, msg="Pago No realizado correctamente")
        self.assertEqual(primera_linea3.deuda_acum, 0.00, msg="Deuda Acumulada incorrecto")
        self.assertEqual(primera_linea3.payment_state, "pagado", msg="El estado del pago no fue registrado correctamente")
        self.assertEqual(primera_linea3.interes_acum, 0.00, msg="Interes Acumulado incorrecto")
        self.assertEqual(primera_linea3.capital_acum, 0.00, msg="Capital Acumulado incorrecto")
        self.assertTrue(primera_linea3.payment_date, msg="Fecha Pago incorrecto")

        _logger.log(logging.INFO, "Test2 verificando pagos pendientes del segundo pago")
        self.assertEqual(record_venta_credito.numero_pagos, 0, msg="Pagos no registrados correctamente")
        self.assertEqual(record_venta_credito.state, "pagado", msg="El estado del credito no fue registrado correctamente")
        
        
