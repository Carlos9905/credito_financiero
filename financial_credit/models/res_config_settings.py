from odoo import models, api, fields
from datetime import datetime
from dateutil.relativedelta import relativedelta

class FinancialCreditAjustes(models.TransientModel):
    _inherit = 'res.config.settings'

    tipo_mora = fields.Selection(string="Tipo de mora",selection=[("importe", "Importe"),("porcentage", "Porcentage"),],default="porcentage")
    periodo = fields.Selection(string="Perído",selection=[("sem", "Semanal"), ("men", "Mensual"), ("dia", "Diario")],default="dia")
    deuda_mayor = fields.Float("Deuda mayor a ")
    importe = fields.Float("Importe")
    porcentaje = fields.Float("Porcentaje")
    mora_product_id = fields.Many2one("product.product","Producto Mora",default=lambda self: self.env["product.product"].search([("default_code", "=", "MOR_CF")]).id)
    interes_product_id = fields.Many2one("product.product","Producto Interes",default=lambda self: self.env["product.product"].search([("default_code", "=", "INT_CF")]).id)
    lim_max_mora = fields.Integer("Limite máximo de moras")
    flujo_credito = fields.Selection(string="Flujo de crédito",selection=[("nada", "Nada"),("confirm_sale", "Solo confirmar Orden de Venta"),("confirm_albaran", "Confirmar Orden de Venta y Confirmar Albarán"),],default="confirm_sale",)
    aprobar_entregar = fields.Boolean("Aprobar y entregar", default=False)
    moras_automaticas = fields.Boolean("Moras automaticas", default=True)
    buscar_cliente_por = fields.Selection(string="Buscar cliente por", selection=[('name','Nombre'),('vat','Identificación'),('phone','Teléfono')])
    tipo_amortiazacion = fields.Selection(string="Tipo de amortización", selection=[("lineal", "Lineal"), ("compuesta", "Compuesta")], default="lineal")
    dias_notificacion = fields.Integer(string="Notificación")
    usa_opciones_pago = fields.Boolean(string="Usar opción de pago", default=False)

    module_sale_order_lot_selection = fields.Boolean("Usar Lotes/n° Serie en las ventas")

    @api.model
    def get_values(self):
        res = super(FinancialCreditAjustes, self).get_values()
        res.update(tipo_mora = self.env['ir.config_parameter'].sudo().get_param('financial_credit.tipo_mora'))
        res.update(periodo = self.env['ir.config_parameter'].sudo().get_param('financial_credit.periodo'))
        res.update(deuda_mayor = self.env['ir.config_parameter'].sudo().get_param('financial_credit.deuda_mayor'))
        res.update(importe = self.env['ir.config_parameter'].sudo().get_param('financial_credit.importe'))
        res.update(porcentaje = self.env['ir.config_parameter'].sudo().get_param('financial_credit.porcentaje'))
        #res.update(mora_product_id = self.env['ir.config_parameter'].sudo().get_param('financial_credit.mora_product_id'))
        #res.update(interes_product_id = self.env['ir.config_parameter'].sudo().get_param('financial_credit.interes_product_id'))
        res.update(lim_max_mora = self.env['ir.config_parameter'].sudo().get_param('financial_credit.lim_max_mora'))
        res.update(flujo_credito = self.env['ir.config_parameter'].sudo().get_param('financial_credit.flujo_credito'))
        res.update(aprobar_entregar = self.env['ir.config_parameter'].sudo().get_param('financial_credit.aprobar_entregar'))
        res.update(moras_automaticas = self.env['ir.config_parameter'].sudo().get_param('financial_credit.moras_automaticas'))
        res.update(buscar_cliente_por = self.env['ir.config_parameter'].sudo().get_param('financial_credit.buscar_cliente_por'))
        res.update(tipo_amortiazacion = self.env['ir.config_parameter'].sudo().get_param('financial_credit.tipo_amortiazacion'))
        res.update(dias_notificacion = int(self.env['ir.config_parameter'].sudo().get_param('financial_credit.dias_notificacion')))
        res.update(usa_opciones_pago = self.env['ir.config_parameter'].sudo().get_param('financial_credit.usa_opciones_pago'))
        return res
    
    def set_values(self):
        res = super(FinancialCreditAjustes, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.tipo_mora', self.tipo_mora)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.periodo', self.periodo)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.deuda_mayor', self.deuda_mayor)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.importe', self.importe)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.porcentaje', self.porcentaje)
        #self.env['ir.config_parameter'].sudo().set_param('financial_credit.mora_product_id', self.mora_product_id)
        #self.env['ir.config_parameter'].sudo().set_param('financial_credit.interes_product_id', self.interes_product_id)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.lim_max_mora', self.lim_max_mora)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.flujo_credito', self.flujo_credito)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.aprobar_entregar', self.aprobar_entregar)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.moras_automaticas', self.moras_automaticas)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.buscar_cliente_por', self.buscar_cliente_por)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.tipo_amortiazacion', self.tipo_amortiazacion)
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.dias_notificacion', int(self.dias_notificacion))
        self.env['ir.config_parameter'].sudo().set_param('financial_credit.usa_opciones_pago', self.usa_opciones_pago)
        return res
#Aqui iran los crons de las moras
class CronFinancialCredit(models.Model):
    _name = "cron.financial.credit"
    _description = "Cron para módulo de créditos"
    def _cron_pagos_atrasados(self):
        #Obtener la fecha en al que se esta ejecutando en el cron
        current_date = datetime.strptime(str(datetime.now().date()), "%Y-%m-%d").date()
        lineas = self.env['lineas.credito'].search([('payment_state', '=', 'pendiente')])
        fechas = lineas.filtered(lambda fecha: fecha.fecha_pago < current_date)
        for fech in fechas:
            fech.write({
                'payment_state':'retrasado'
            })

    def _cron_notificacion_pagos(self):
        dias = self.env['ir.config_parameter'].sudo().get_param('financial_credit.dias_notificacion')
        today = datetime.now().date()
        next_date = today + relativedelta(days=int(dias))
        lineas = self.env['lineas.credito'].search([('payment_state', '=', 'pendiente')])
        fechaProxima = lineas.filtered(lambda fecha: fecha.fecha_pago == next_date)
        for fecha in fechaProxima:
            fecha.send_notification_payment()
    
    def _cron_update_balance(self):
        creditos = self.env['financial.credit'].search([("state", "in", ["pendiente", "pagado","rechazado", "cancelado"]),("tipo_doc", "=", "ven")])
        for credit in creditos:
            invoice_capital = self.env["account.move"].search([
                ("credito_id", "=", credit.id),
                ("payment_reference", "=", credit.numero + "(Capital)")
            ])
            invoice_interes = self.env["account.move"].search([
                ("credito_id", "=", credit.id),
                ("payment_reference", "=", credit.numero + "(Interes)"),
            ])
            credit.write({
                "balance": invoice_capital.amount_residual + invoice_interes.amount_residual
            })
        