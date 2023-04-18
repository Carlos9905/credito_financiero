from datetime import datetime
from odoo import fields
from odoo.tests import Form, tagged, common
import pytz

@tagged('post_install', '-at_install')
class TestCredit(common.TransactionCase):
    """"
    Test del módelo de credito, asegura la eficiencia del código
    """

    @classmethod
    def setUpClass(cls):
        super(TestCredit, cls).setUpClass()
        cls.credit = cls.env["financial.credit"]

        cls.res_partner = cls.env["res.partner"]
        cls.product_id = cls.env["product.product"]
        cls.frecuencia_id = cls.env["frecuencia.credito"]
        cls.cuotas_id = cls.env["cuotas.credito"]
        cls.tipo_credito_id = cls.env["tipo.credito"]

        cls.carlos = cls.res_partner.create(dict(name="Carlos", vat="BE0477472701", phone="56902351"))
        cls.martha = cls.res_partner.create(dict(name="Martha", vat="BE0477472702", phone="55985397"))
        
        cls.interes_producto = cls.product_id.create(dict(name="Interés", list_price=1.0, standard_price=1.0, default_code="INT_CF", type="service"))
        cls.financiamiento_producto = cls.product_id.create(dict(name="Financiamiento", list_price=1.0, standard_price=1.0, default_code="SER_CF", type="service"))

        cls.cuota3 = cls.cuotas_id.create(dict(nombre="Cuota 3", numero=3))
        cls.cuota6 = cls.cuotas_id.create(dict(nombre="Cuota 6", numero=6))

        cls.interes_1_35 = cls.tipo_credito_id.create(dict(name="Intres 1.35%", interes=0.013500000000000002, max_financiar=1))

        cls.frecuencia_mensual = cls.frecuencia_id.create(dict(nombre="Mensual", tipo_frecuencia="meses", cuotas_ids=[(6, 0, [cls.cuota3.id, cls.cuota6.id])]))

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
        

    def test_crear_credito(self):
        """
        Test de creación de un credito financiero
        """
        Credit = self.credit.with_user(self.user)
        venta_credito = Form(Credit,view="financial_credit.view_financial_credit_form")
        venta_credito.producto_id = self.env.ref("financial_credit.servi_finan_product")
        venta_credito.monto = 6000.00
        venta_credito.telefono = "56902351"
        
        print(self.carlos.name)
        print(venta_credito.numero)
        #self.assertEqual(record_venta_credito.monto, 6000.00)