from odoo import fields, models

class Doduments(models.Model):
    _name = "documents.credit"
    _description = "Documentos de creditos"
    
    name = fields.Char("Descripcion")
    archivo = fields.Binary("Archivo")

    credito_id = fields.Many2one("financial.credit",string="Crédito")