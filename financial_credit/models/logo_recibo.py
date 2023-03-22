from odoo import api, models, fields

class LogoRecibo(models.Model):
    _inherit = 'res.company'

    logo_recibo = fields.Binary(string="Logo Recibo", readonly=False, store=True)