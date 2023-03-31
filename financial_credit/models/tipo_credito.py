from odoo import fields, api, models

class TiposCreditos(models.Model):
    _name = "tipo.credito"
    _description = "Tipos de créditos financieros"

    name = fields.Char("Nombre")
    interes = fields.Float("Interés Mensual")
    max_financiar = fields.Float("Porcentaje máximo a financiar", help="Si no requiere de un monto inicial dejarlo en 100%")
    currency_id = fields.Many2one('res.currency', readonly=True,default=lambda self:self.env.user.company_id.currency_id)
    sequence = fields.Integer("Secuencia")
