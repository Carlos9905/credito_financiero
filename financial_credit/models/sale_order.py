from odoo import fields, api, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    credito_id = fields.One2many("financial.credit", "sale_id", string="Créditos")

    cuenta_financial_credit = fields.Float(
        "Cuenta de Créditos", compute="_cuenta_financial_credit"
    )
    
    es_contado = fields.Boolean("Venta al contado", default=False)
    estado_solicitud = fields.Char(
        string="Estado de la solicitud",
        store=True
    )
    
    @api.depends("credito_id.state")
    def _estado_soli(self):
        for record in self:
            if record.credito_id:
                record.estado_solicitud = record.credito_id.state
            else:
                pass

    def ver_boton_credito(self):
        if self.credito_id:
            action = {
                "name": "Créditos",
                "res_model": "financial.credit",
                "type": "ir.actions.act_window",
                "domain": [("sale_id", "=", self.id)],
                "view_mode": "tree,form",
            }
            action["context"] = {
                "search_sale_id": self.id,
                "default_sale_id": self.id,
            }
            action["domain"] = [("sale_id", "=", self.id)]
            documentos = self.mapped("credito_id")
            if len(documentos) == 1:
                action["view_mode"] = "form"
                action["res_id"] = documentos.id
            return action
        else:
            nombre = "Order de crédito para " + self.partner_id.name
            producto = self.env["sale.order.line"].search([("order_id", "=", self.id)])
            sale_lot = self.env['ir.module.module'].search([('name','=','sale_order_lot_selection')])
            data = {
                    "sale_id": self.id,
                    "tipo_doc": "ven",
                    "monto":producto.price_unit,
                    "producto_id": producto.product_id.id,
                    "telefono":self.partner_id.phone,
                    "cliente_id": self.partner_id.id,
                } if sale_lot.state != "installed" else {
                    "sale_id": self.id,
                    "tipo_doc": "ven",
                    "monto":producto.price_unit,
                    "producto_id": producto.product_id.id,
                    "numero_serie": producto.lot_id.name,
                    "telefono":self.partner_id.phone,
                    "cliente_id": self.partner_id.id,
                }
            credit = self.env["financial.credit"].create(data)
            action = {
                "name": nombre,
                "res_model": "financial.credit",
                "type": "ir.actions.act_window",
                "domain": [("sale_id", "=", credit.id)],
                "view_mode": "form",
                "res_id": credit.id,
            }
            action["context"] = {
                "search_default_sale_id": self.id,
                "default_sale_id": self.id,
            }
            return action

    def _cuenta_financial_credit(self):
        for record in self:
            record.cuenta_financial_credit = (self.env["financial.credit"].search([("sale_id", "=", record.id)]).deuda_total)
    
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for record in self:
            if record.es_contado != True:
                creditos = self.env["financial.credit"].search([("sale_id", "=", record.id)])
                if creditos:
                    if creditos.state != "aprobado":
                        raise UserError(_(
                            "La Orden de Crédito no esta aprobada, solicita una aprobación para continuar con la venta"
                        ))
                else:
                    raise UserError(_(
                        "Esta es una venta al crédito, solicita uno para confirmar la venta"
                    ))
            else:
                return res