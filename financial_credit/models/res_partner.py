from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = "res.partner"

    referencia_personal = fields.Char("Referencia perosonal")
    dpi = fields.Char("DPI")
    telefono_referencia = fields.Char("Télefono de la referencia")
    tipo_relacion = fields.Selection(
        string="Tipo de relación",
        selection=[
            ("papa", "Padre"),
            ("mama", "Madre"),
            ("abuelo", "Abuelo /a"),
            ("tio", "Tío /a"),
            ("primo", "Primo /a"),
            ("sobrino", "Sobrino /a"),
            ("esposa", "Esposo /a"),
            ("amigo", "Amigo /a"),
            ("tutor", "Tutor /a"),
            ("otro", "Otro"),
        ],
    )

    @api.constrains('phone')
    def _check_unique_phone(self):
        for record in self:
            if record.phone:
                same_phone = self.search([('phone', '=', record.phone), ('id', '!=', record.id)])
                if same_phone:
                    raise UserError(_("El número de teléfono ya está registrado en otro contacto"))