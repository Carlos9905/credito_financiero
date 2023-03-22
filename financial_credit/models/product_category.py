from odoo import fields, models, api

class ProductCategoria(models.Model):
    _inherit = "product.category"

    interes = fields.Float("Taza de interés")