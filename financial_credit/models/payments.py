from odoo import fields, api, models, _
from odoo.exceptions import UserError

from datetime import datetime
import pytz

from decimal import Decimal,ROUND_HALF_UP

class Payments(models.Model):
    _name = "payment.credit"
    _description = "Pagos de creditos"
    _rec_name = "number"
    _order = 'fecha desc, id desc'
    _inherit = ["mail.thread", "mail.activity.mixin"]

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.user.company_id.id
    )

    state = fields.Selection(
        string="Estado Del Documento",
        selection=[
            ("borrador", "Borrador"),
            ("validado", "Validado"),
            ("pagado", "Pagado"),
        ],
        default="borrador"
    )
    type_doc = fields.Selection(string="Tipo de documento",selection=[("pago_credi", "Pago por crédito"), ("pago", "Pago normal")])
    flujo_pago = fields.Selection(string='Opciones de pago', selection=[
        ('normal', 'Normal'),('interes', 'Solo Interés'),('capital', 'Solo Capital')
    ], default='normal')

    number = fields.Char("Número", default="Nuevo pago", readonly=True)
    cliente_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        compute="get_cliente",
        store=True,
        readonly=False,
    )
    telefono = fields.Char("Teléfono")
    ref = fields.Char("Memo", help="Referencia del pago")
    credit_id = fields.Many2one("financial.credit", string="Crédito")
    cuota_fija = fields.Float(
        "Cuota fija", related="credit_id.cuota_fija", store=False, readonly=True
    )
    total_pagar = fields.Float(
        "Deuda", related="credit_id.deuda_total", store=False, readonly=True
    )

    monto = fields.Float("Pago Total")
    balance = fields.Float("Balance Actual", compute="_get_balance", store=True)
    deuda_actual = fields.Float("A pagar", compute="_get_deuda_actual", store=True)
    fecha = fields.Date("Fecha", default=lambda self: datetime.now(pytz.timezone(self.env.user.tz)))
    user_id = fields.Many2one("res.users", string="Vendedor", default=lambda self: self.env.uid, readonly=True)
    notas = fields.Text("Notas")
    currency_id = fields.Many2one(
        "res.currency",
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        default=lambda self: self.env["account.journal"].search(
            [("name", "=", "Banco")]
        ),
    )

    linas_pagos_ids = fields.One2many(
        "lineas.credito",
        "paymet_id",
        string="Pagos",
        related="credit_id.lineas_pagos_ids",
    )
    usa_opciones_pago = fields.Boolean("Usa Opciones de pago", compute="set_opcion_pago", store=True)

    # Metodos de odoo
    def set_opcion_pago(self):
        valor = self.env['ir.config_parameter'].sudo().get_param('financial_credit.usa_opciones_pago')
        for record in self:
            record.usa_opciones_pago = bool(valor)
    
    """@api.model
    def create(self, vals):
        if (vals.get("number") == "Borrador") and vals.get("state") == "borrador":
            vals["number"] = "Borrador"#self.env["ir.sequence"].next_by_code("payment.credit") or ("Nuevo pago")
        elif (vals.get("number") == "Nuevo pago") and vals.get("state") == "borrador":
            vals["number"] = "Borrador"
        return super(Payments, self).create(vals)"""

    @api.ondelete(at_uninstall=False)
    def _borrar_credito(self):
        for credito in self:
            if credito.state != "borrador":
                raise UserError(
                    _(
                        "No puedes borrar un documento de pago que ya esta validada o pagada"
                    )
                )
    
    @api.constrains("flujo_pago")
    def validation_date(self):
        for record in self:
            invoice_capital = self.env["account.move"].search(
                [
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Capital)")
                ]
            )
            invoice_interes = self.env["account.move"].search(
                [
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Interes)"),
                ]
            )
            if invoice_interes.amount_residual == 0.0 and record.flujo_pago in ("normal", "interes"):
                raise UserError(
                    _("La factura de interes ya está cancelada, por favor seleccione otra opción de pago")
                )
            elif invoice_capital.amount_residual == 0.0 and record.flujo_pago in ("normal", "capital"):
                raise UserError(
                    _("La factura de capital ya está cancelada, por favor seleccione otra opción de pago")
                )

    """
    @api.constrains("monto")
    def validation_payment(self):
        for rec in self:
            print(rec.monto)
            if rec.monto < rec.deuda_actual:
                raise UserError(
                    _("El monto ingresado no puede ser menor a la cuota fija")
                )
    """
    # Botones
    def registrar_pago(self):
        for record in self:
            # Facturas
            invoice_capital = self.env["account.move"].search(
                [
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Capital)")
                ]
            )
            invoice_interes = self.env["account.move"].search(
                [
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Interes)"),
                ]
            )

            lineas = self.env["lineas.credito"].search([("credito_id", "=", record.credit_id.id)])

            # Variables y listas para la lógica de la deuda, capital y interés acumulado
            cuota_fija = round(record.cuota_fija,2)
            monto = record.monto
            deuda_acumulada = lineas.filtered(lambda p: p.payment_state in ("pendiente", "pago_par","retrasado")).mapped("deuda_acum")
            interes_acumulado = lineas.filtered(lambda p: p.payment_state in ("pendiente", "pago_par","retrasado")).mapped("interes_acum")
            capital_acumulado = lineas.filtered(lambda p: p.payment_state in ("pendiente", "pago_par","retrasado")).mapped("capital_acum")       
            
            """Logica para cada caso de flujo"""
            recurso = self.forma_pago(monto, cuota_fija, deuda_acumulada, interes_acumulado,capital_acumulado, forma=record.flujo_pago)
            
            # Actualizar la tabla de pagos, con los datos obtenidos
            num = lineas.filtered(lambda cuotas: cuotas.payment_state in ("pendiente", "pago_par")).mapped("numero")
            n = 0
            for i in num:
                datos = lineas.filtered(lambda cuotas: cuotas.payment_state in ("pendiente", "pago_par") and cuotas.numero == i)
                # NORMAL
                if record.flujo_pago == 'normal':
                    datos.write({
                        "deuda_acum": recurso['deuda_acumulada'][n],
                        "payment_amount": recurso['pagos'][n],
                        "capital_acum": recurso['capital_acumulado'][n],
                        "interes_acum": recurso['interes_acumulado'][n],
                    })
                # INTERES
                elif record.flujo_pago == 'interes':
                    datos.write({
                        "deuda_acum": recurso['deuda_acumulada'][n],
                        "payment_amount": recurso['pagos_de_interes'][n] if datos.payment_amount == 0.0 else datos.payment_amount + recurso['pagos_de_interes'][n],
                        "capital_acum": recurso['capital_acumulado'][n],
                        "interes_acum": recurso['interes_acumulado'][n],
                    })
                # CAPITAL
                else:
                    datos.write({
                        "deuda_acum": recurso['deuda_acumulada'][n],
                        "payment_amount": recurso['pagos_de_capital'][n] if datos.payment_amount == 0.0 else datos.payment_amount + recurso['pagos_de_capital'][n],
                        "capital_acum": recurso['capital_acumulado'][n],
                        "interes_acum": recurso['interes_acumulado'][n],
                    })
                n += 1

            # Pagos
            if (sum(recurso['pagos_de_capital']) > 0):
                pago_capital = {
                    "reconciled_invoice_ids": [(4, invoice_capital.id)],
                    "partner_id": record.cliente_id.id,
                    "amount": sum(recurso['pagos_de_capital']) if invoice_capital.amount_residual > 0.5 else sum(recurso['pagos_de_capital']) + invoice_capital.amount_residual,
                    "date": record.fecha,
                    "journal_id": record.journal_id.id,
                    "payment_type": "inbound",
                    "ref": record.ref
                }
                record.credit_id.payment_register(pago_capital, invoice_capital)
            if (sum(recurso['pagos_de_interes']) > 0):
                pago_interes = {
                    "reconciled_invoice_ids": [(4, invoice_interes.id)],
                    "partner_id": record.cliente_id.id,
                    "amount": sum(recurso['pagos_de_interes']) if invoice_interes.amount_residual > 0.5 else sum(recurso['pagos_de_interes']) + invoice_interes.amount_residual,
                    "date": record.fecha,
                    "journal_id": record.journal_id.id,
                    "payment_type": "inbound",
                    "ref": record.ref
                }
                record.credit_id.payment_register(pago_interes, invoice_interes)
            record.state = "pagado"

            # Si la factura de capital y interes esta pagada, Pasar a pagado el crédito
            if (invoice_capital.payment_state == "paid" and invoice_interes.payment_state == "paid"):
                credito = self.env["financial.credit"].search([("id", "=", record.credit_id.id)])
                credito.write({"state": "pagado"})

    def action_confirm(self):
        for record in self:
            if record.monto > 0:
                record.state = "validado"
                record.number = self.env["ir.sequence"].next_by_code("payment.credit")
            else:
                raise UserError(_("Monto a pagar no puede ser 0"))

    def imprimir_ticket(self):
        return self.env.ref("financial_credit.action_ticket_pago").report_action(self)

    # Calculos
    @api.depends("telefono")
    def get_cliente(self):
        for record in self:
            if record.telefono:
                cliente = self.env["res.partner"].search(
                    [("phone", "=", record.telefono)]
                )
                if cliente:
                    record.cliente_id = cliente.id

    @api.depends("credit_id")
    def _get_balance(self):
        for record in self:
            # Facturas
            if record.credit_id:
                invoice_capital = self.env["account.move"].search([
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Capital)")
                ])
                invoice_interes = self.env["account.move"].search([
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Interes)"),
                ])
                record.balance = (invoice_capital.amount_residual + invoice_interes.amount_residual)
            else:
                pass
    
    @api.depends("credit_id")
    def _get_deuda_actual(self):
        for record in self:
            if record.credit_id:
                pagos = self.env["lineas.credito"].search([
                    ("credito_id", "=", record.credit_id.id),
                ])
                pagos_prox = pagos.filtered(lambda p: p.payment_state != "pagado")
                _pagos = pagos_prox.mapped("deuda_acum")
                record.deuda_actual = round(_pagos[0], 2)
                #record.monto = record.deuda_actual
            else:
                pass

    def forma_pago(self,monto:float,cuota_fija:float,deuda_acumulada:list, interes_acumulado:list,capital_acumulado:list, forma:str='normal') -> dict:
        
        """
        FORMAS DE PAGOS
        :param monto: Monto que el cliente va a pagar
        :param cuota_fija: Cuota fija del crédito
        :param deuda_acumulada: Deuda acumulada del cliente
        :param interes_acumulado: Interés acumulado del cliente
        :param capital_acumulado: Capital acumulado del cliente
        :param forma: Forma de pago
        """

        if forma == 'normal':
            restante = monto
            pagos = [0 for i in range(len(deuda_acumulada))]
            pagos_de_interes = [0 for i in range(len(deuda_acumulada))]
            pagos_de_capital = [0 for i in range(len(deuda_acumulada))]
            for i in range(len(deuda_acumulada)):
                if restante >= cuota_fija:
                    deuda_acumulada[i] = 0
                    pagos[i] = cuota_fija
                    restante = float(Decimal(restante - cuota_fija).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                else:
                    deuda_acumulada[i] = float(Decimal(deuda_acumulada[i] - restante).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos[i] = restante
                    restante = 0
                    break

            # Saldar interes_acumulado y capital_acumulado
            for i in range(len(interes_acumulado)):
                if monto >= interes_acumulado[i]:
                    monto = float(Decimal(monto - interes_acumulado[i]).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_interes[i] = interes_acumulado[i]
                    interes_acumulado[i] = 0
                else:
                    interes_acumulado[i] = float(Decimal(interes_acumulado[i] - monto).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_interes[i] = monto
                    monto = 0
                if monto >= capital_acumulado[i]:
                    monto = float(Decimal(monto - capital_acumulado[i]).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_capital[i] = capital_acumulado[i]
                    capital_acumulado[i] = 0
                else:
                    capital_acumulado[i] = float(Decimal(capital_acumulado[i] - monto).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_capital[i] = monto
                    monto = 0

            return {
                "pagos": pagos,
                "deuda_acumulada":deuda_acumulada,
                "pagos_de_interes": pagos_de_interes,
                "pagos_de_capital": pagos_de_capital,
                "interes_acumulado": interes_acumulado,
                "capital_acumulado": capital_acumulado
            }
    
        elif forma == 'interes':
            restante = monto
            pagos = [0 for i in range(len(deuda_acumulada))]
            pagos_de_interes = [0 for i in range(len(deuda_acumulada))]
            pagos_de_capital = [0 for i in range(len(deuda_acumulada))]
            
            # Saldar interes_acumulado y capital_acumulado
            for i in range(len(interes_acumulado)):
                if monto >= interes_acumulado[i]:
                    monto = float(Decimal(monto - interes_acumulado[i]).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_interes[i] = interes_acumulado[i]
                    deuda_acumulada[i] -= interes_acumulado[i]
                    interes_acumulado[i] = 0
                else:
                    interes_acumulado[i] = float(Decimal(interes_acumulado[i] - monto).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_interes[i] = monto
                    monto = 0

            return {
                "pagos": pagos,
                "deuda_acumulada":deuda_acumulada,
                "pagos_de_interes": pagos_de_interes,
                "pagos_de_capital": pagos_de_capital,
                "interes_acumulado": interes_acumulado,
                "capital_acumulado": capital_acumulado
            }
        elif forma == 'capital':
            restante = monto
            pagos = [0 for i in range(len(deuda_acumulada))]
            pagos_de_interes = [0 for i in range(len(deuda_acumulada))]
            pagos_de_capital = [0 for i in range(len(deuda_acumulada))]             

            # Saldar interes_acumulado y capital_acumulado
            for i in range(len(capital_acumulado)):
                if monto >= capital_acumulado[i]:
                    monto = float(Decimal(monto - capital_acumulado[i]).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_capital[i] = capital_acumulado[i]
                    deuda_acumulada[i] -= capital_acumulado[i]
                    capital_acumulado[i] = 0
                else:
                    capital_acumulado[i] = float(Decimal(capital_acumulado[i] - monto).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
                    pagos_de_capital[i] = monto
                    monto = 0
            return {
                "pagos": pagos,
                "deuda_acumulada":deuda_acumulada,
                "pagos_de_interes": pagos_de_interes,
                "pagos_de_capital": pagos_de_capital,
                "capital_acumulado": capital_acumulado,
                "interes_acumulado": interes_acumulado,
            }
