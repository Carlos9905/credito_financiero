from odoo import fields, models, api


class Cuotas(models.Model):
    _name = "cuotas.credito"
    _description = "Coutas de crédito"
    _rec_name = "nombre"

    nombre = fields.Char("Nombre")
    numero = fields.Integer("Número de cuotas")

class Frecuencia(models.Model):
    _name = "frecuencia.credito"
    _description = "Frecuencias de pagos"
    _rec_name = "nombre"

    nombre = fields.Char("Nombre")
    tipo_frecuencia = fields.Selection(
        string="Tipo de frecuencia",
        selection=[
            ("semanas", "Semanales"),
            ("quincenas", "Quincenales"),
            ("meses", "Mensuales"),
        ],
    )
    descripcion = fields.Text("Descripcion")
    cuotas_ids = fields.Many2many("cuotas.credito", string="Cuotas")

#Codigo by Carlos Aguilar