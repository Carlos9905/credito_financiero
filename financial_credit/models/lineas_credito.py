from datetime import datetime
from odoo import fields, api, models
import pytz


class LineasCredito(models.Model):
    _name = "lineas.credito"
    _description = "Lineas de crédito"
    _rec_name = "numero"

    numero = fields.Integer("N° Cuota")
    contacto = fields.Many2one("res.partner", string="Cliente")
    cuota_inicial = fields.Float("Capital vivo")
    cuota_fija = fields.Float("Cuota Fija")
    interes = fields.Float("Interés")
    capital = fields.Float("Capital")
    fecha_pago = fields.Date("Fecha De Pago Esperada")

    deuda_acum = fields.Float("Pago Pendiente")
    capital_acum = fields.Float("Capital pendiente")
    interes_acum = fields.Float("Interes pendiente")

    payment_state = fields.Selection(
        string="Estado del Pago",
        selection=[
            ("pagado", "Pagado"),
            ("pago_par", "Parcial"),
            ("pendiente", "Pendiente"),
            ("retrasado", "Retrasado"),
            ("mora", "Mora")
        ],
        compute="cambiar_estado",
        store = True
    )
    payment_date = fields.Date("Fecha pagada")
    payment_amount = fields.Float("Monto pagado")
    mora = fields.Char("Mora")

    credito_id = fields.Many2one("financial.credit", string="Crédito de Origen")
    paymet_id = fields.Many2one("payment.credit", string="Pago al que pertenece")

    @api.depends("deuda_acum")
    def cambiar_estado(self):
        for record in self:
            if record.deuda_acum == 0:
                record.payment_state = "pagado"
                record.payment_date = datetime.now(pytz.timezone(self.env.user.tz))
            elif record.deuda_acum > 0 and record.deuda_acum < round(record.cuota_fija,2):
                record.payment_state = "pago_par"
                record.payment_date = datetime.now(pytz.timezone(self.env.user.tz))
            elif record.deuda_acum == round(record.cuota_fija,2):
                record.payment_state = "pendiente"
#Codigo by Carlos Aguilar