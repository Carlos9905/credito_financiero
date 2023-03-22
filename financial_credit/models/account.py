from odoo import models, api, fields

class AccountMove(models.Model):
    _inherit="account.move"

    credito_id = fields.Many2one("financial.credit", string="Orden de credito")

#Codigo by Carlos Aguilar