from odoo import fields, api, models, _
from odoo.exceptions import UserError

from datetime import datetime
import pytz

from decimal import Decimal,ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_DOWN, ROUND_UP

class Payments(models.Model):
    _name = "payment.credit"
    _description = "Pagos de creditos"
    _rec_name = "number"
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
    )
    type_doc = fields.Selection(
        string="Tipo de documento",
        selection=[("pago_credi", "Pago por crédito"), ("pago", "Pago normal")],
    )

    number = fields.Char("Número", default="Nuevo pago", readonly=True)
    cliente_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        compute="get_cliente",
        store=True,
        readonly=False,
    )
    telefono = fields.Char("Teléfono")
    credit_id = fields.Many2one("financial.credit", string="Crédito")
    cuota_fija = fields.Float(
        "Cuota fija", related="credit_id.cuota_fija", store=False, readonly=True
    )
    total_pagar = fields.Float(
        "Deuda", related="credit_id.deuda_total", store=False, readonly=True
    )

    monto = fields.Float("Pago Total")
    balance = fields.Float("Balance Actual", compute="_get_balance", store=True)
    deuda_actual = fields.Float(
        "A pagar", compute="_get_deuda_actual", store=True
    )
    fecha = fields.Date(
        "Fecha", default=lambda self: datetime.now(pytz.timezone(self.env.user.tz))
    )
    user_id = fields.Many2one(
        "res.users", string="Vendedor", default=lambda self: self.env.uid, readonly=True
    )
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

    # Metodos de odoo
    @api.model
    def create(self, vals):
        if vals.get("number", ("Nuevo pago")) == ("Nuevo pago"):
            vals["number"] = self.env["ir.sequence"].next_by_code("payment.credit") or (
                "Nuevo pago"
            )
        vals["state"] = "borrador"
        return super(Payments, self).create(vals)

    @api.ondelete(at_uninstall=False)
    def _borrar_credito(self):
        for credito in self:
            if credito.state != "borrador":
                raise UserError(
                    _(
                        "No puedes borrar un documento de pago que ya esta validada o pagada"
                    )
                )

    @api.constrains("monto")
    def validation_payment(self):
        for rec in self:
            print(rec.monto)
            if rec.monto < rec.deuda_actual:
                raise UserError(
                    _("El monto ingresado no puede ser menor a la cuota fija")
                )

    # Botones
    def registrar_pago(self):
        for record in self:
            # Facturas
            invoice_capital = self.env["account.move"].search(
                [("invoice_origin", "=", record.credit_id.sale_id.name)]
            )
            invoice_interes = self.env["account.move"].search(
                [
                    ("credito_id", "=", record.credit_id.id),
                    ("payment_reference", "=", record.credit_id.numero + "(Interes)"),
                ]
            )

            lineas = self.env["lineas.credito"].search(
                [("credito_id", "=", record.credit_id.id)]
            )

            # Variables y listas para la lógica de la deuda, capital y interés acumulado
            cuota_fija = round(record.cuota_fija,2)
            monto = record.monto
            restante = monto
            deuda_acumulada = lineas.filtered(lambda p: p.payment_state in ("pendiente", "pago_par","retrasado")).mapped("deuda_acum")
            pagos = [0 for i in range(len(deuda_acumulada))]
            interes_acumulado = lineas.filtered(lambda p: p.payment_state in ("pendiente", "pago_par","retrasado")).mapped("interes_acum")
            capital_acumulado = lineas.filtered(lambda p: p.payment_state in ("pendiente", "pago_par","retrasado")).mapped("capital_acum")

            # Lista para crear pagos
            pagos_de_interes = [0 for i in range(len(deuda_acumulada))]
            pagos_de_capital = [0 for i in range(len(deuda_acumulada))]        
            
            """
            Lo que se busca es almacenar el monto restante de un pago parcial, ya que un cliente puede abonar una cuota media parte de la que sigue
            con las listas de interes_acumulado, capital_acumulado y deuda acumulado se logre hacer eso.
            -Las deudas acumuladas es el mismo que las cuotas fijas, se usa para saber cuanto quedará debiendo el cliente para su proximo cobro
            -Los pagos que se hagan se agregan al array de pagos para posteriormente sea mas facil agregarlos en la BD
            
            Se divide la operacion en dos for, ya que la operacion de la deuda acumulada es independiente de los intereces y el capita acumulado
            lo que se hace es lo siguiente:
            
            Deuda acumulada:
                Si el restante que al inicio del for toma el valor del monto, es mayor o igual a la cuota fija, quiere decir que hay dinero
                suficiente para saldar la deuda de la interación, por tanto el array deuda_acumulada se le asigna el valor 0, se registra
                el pago realizado en el array pagos, dandole el valor de la cuota fija, y a la variable restante se resta la cuota fija.
                En caso contrario, si el restante no mayor o igual a la cuota fija quiere decir que ya no hay dinero para saldar la deuda acumulada,
                por tanto a la deuda acumulada se le resta el valor de la variable restante, es decir el valor que haya quedado de esa variable
                y se registra en el array pagos el valor del restante puesto que ese es el valor pagado
            
            Interés y captial acumulado:
                Lo que se hace en este for es verificar que el monto que el cliente este dado es suficiente para saldar el interes primeramente,
                ya que la dinamica es primero pagar el interés y luego el capital.
                entonces si el monto e suficiente, quiere decir que hay el dinero suficiente para saldar ese interés, se le resta 
                a la variable monto el valor del interés de esa iteración y saldamos el interés asignando el valor 0 a ese array, pasamos al capital,
                donde si verificamos que el valor del monto, es decir el sobrante despues de pagar el interés es suficiente para pagar el capital
                si es asi entonces le restamos al monto el valor del capital de esa iteración y se asigna el valor 0 a ese array de capital.
                Volvemos al interés y si no hay dinero suficiente para saldarlo, solo le restamos el valor del monto osea el restante de las otras
                iteraciones y se le asigna al valor 0 al monto, puesto que se lo asignamos todo al interes
                a continuación, en el capital, si el monto (restante de las otras operaciones) no es suficiente para saldarlo, le restamos el valor
                del monto y se asigna el valor 0 al monto, ya se ocupo todo para saldar el capital
            """
            
            # Saldar deuda_acumulada
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

            # Actualizar la tabla de pagos, con los datos obtenidos
            num = lineas.filtered(lambda cuotas: cuotas.payment_state in ("pendiente", "pago_par")).mapped("numero")
            n = 0
            for i in num:
                datos = lineas.filtered(lambda cuotas: cuotas.payment_state in ("pendiente", "pago_par")and cuotas.numero == i)
                datos.write(
                    {
                        "deuda_acum": deuda_acumulada[n],
                        "payment_amount": pagos[n],
                        "capital_acum": capital_acumulado[n],
                        "interes_acum": interes_acumulado[n],
                    }
                )
                n += 1

            # Pagos
            pago_capital = {
                "reconciled_invoice_ids": [(4, invoice_capital.id)],
                "partner_id": record.cliente_id.id,
                "amount": sum(pagos_de_capital),
                "date": record.fecha,
                "journal_id": record.journal_id.id,
                "payment_type": "inbound",
                "ref": record.number + " (Capital)",
            }
            pago_interes = {
                "reconciled_invoice_ids": [(4, invoice_interes.id)],
                "partner_id": record.cliente_id.id,
                "amount": sum(pagos_de_interes),
                "date": record.fecha,
                "journal_id": record.journal_id.id,
                "payment_type": "inbound",
                "ref": record.number + " (Interés)",
            }
            
            record.credit_id.payment_register(pago_interes, invoice_interes)
            record.credit_id.payment_register(pago_capital, invoice_capital)
            record.state = "pagado"

            # Si la factura de capital y interes esta pagada, Pasar a pagado el crédito
            if (invoice_capital.payment_state == "paid" and invoice_interes.payment_state == "paid"):
                credito = self.env["financial.credit"].search([("id", "=", record.credit_id.id)])
                credito.write({"state": "pagado"})

    def action_confirm(self):
        for record in self:
            record.state = "validado"

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
                invoice_capital = self.env["account.move"].search(
                    [("invoice_origin", "=", record.credit_id.sale_id.name)]
                )
                invoice_interes = self.env["account.move"].search(
                    [
                        ("credito_id", "=", record.credit_id.id),
                        (
                            "payment_reference",
                            "=",
                            record.credit_id.numero + "(Interes)",
                        ),
                    ]
                )
                record.balance = (
                    invoice_capital.amount_residual + invoice_interes.amount_residual
                )
            else:
                pass
    
    @api.depends("credit_id")
    def _get_deuda_actual(self):
        for record in self:
            if record.credit_id:
                pagos = self.env["lineas.credito"].search(
                    [
                        ("credito_id", "=", record.credit_id.id),
                    ]
                )
                pagos_prox = pagos.filtered(lambda p: p.payment_state != "pagado")
                _pagos = pagos_prox.mapped("deuda_acum")
                record.deuda_actual = round(_pagos[0], 2)
                record.monto = record.deuda_actual
            else:
                pass


# Codigo by Oscar Rugama
