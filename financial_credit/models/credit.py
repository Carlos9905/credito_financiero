#Tabla de amortización
from .genera_tabla import amortizacion_lineal, amortizacion_compuesta

# Time
from datetime import datetime
import pytz
from dateutil.relativedelta import relativedelta

# Odoo
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import psycopg2
import logging

_logger = logging.getLogger(__name__)

# Math
from decimal import ROUND_HALF_UP, Decimal, ROUND_UP, ROUND_DOWN
try:
    import numpy_financial._financial as npf
except:
    _logger.debug(
        'La librería de "numpy_financial" no esta instalada\
                 Por favor instalar con "pip3 install numpy_financial".'
    )


class FinancialCredit(models.Model):
    _name = "financial.credit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Credito de financiacion"
    _order = "fecha desc, id desc"
    _rec_name = "numero"

    num_cuota = fields.Integer("Cuotas", related="cuota_id.numero")
    numero_pagos = fields.Integer("Numero de pagos pendiente", compute="numero_pagos_pend")
    numero_facturas = fields.Integer("Facturas", compute="cantidad_factura")
    
    tipo_doc = fields.Selection(string="Tipo de documento",selection=[("cal", "Calculadora"), ("ven", "Venta")])
    state = fields.Selection(
        string="Estado",
        selection=[
            ("borrador", "Borrador"),
            ("solicitud", "Solicitud de Aprobación"),
            ("aprobado", "Aprobado"),
            ("pendiente", "Pagos Pendientes"),
            ("pagado", "Pagado"),
            ("rechazado", "Rechazado"),
            ("cancelado", "Cancelado")
        ],
        default="borrador",
        store=True,
    )
    tipo_amortiazacion = fields.Selection(string="Tipo de amortización", selection=[("lineal", "Lineal"), ("compuesta", "Compuesta")], default=lambda self: self.env['ir.config_parameter'].sudo().get_param('financial_credit.tipo_amortiazacion'))
    
    habiliar_solicitud = fields.Boolean("Solicitud")
    venta_servicio = fields.Boolean("Venta de servicio", compute="cal_venta_servicio", store=True)
    documentos = fields.Boolean("Documentos", compute="verificar_documentos", store=True, copy=False, default=False)

    numero = fields.Char(string="Orden de Crédito", default="Nuevo", readonly=True)
    numero_serie = fields.Char("Número de serie")
    telefono = fields.Char("Teléfono")
    
    fecha = fields.Date("Fecha", default= datetime.now(pytz.timezone('America/Guatemala')))
    fecha_primer_pago = fields.Date("Fecha del primer pago")

    interes_mensual = fields.Float("TEM (%)", related="tipo_credito_id.interes", store=True, help="Tasa de interés mensual")
    precio = fields.Float("Precio", compute="_get_precio", store=True)# Precio del producto
    monto = fields.Float("Monto")
    monto_inicial = fields.Float("Monto Inicial", help="Monto inicial como anticipo para aplicar al crédito")
    total = fields.Float("A Financiar",compute="cal_total",help="Es la resta del precio del producto menos en monto inicial")
    deuda_total = fields.Float("Total",compute="cal_deuda_total",help="Total a pagar por el período establecido")
    cuota_fija = fields.Float("Cuota fija",compute="cal_cuota_fija",help="Frecuencia en la que el cliente dara la cuota")
    total_interes = fields.Float("Total de Interés", compute="cal_total_interes", store=True, help="Intereses")
    max_financiar = fields.Float("% Maximo de Financiamiento", related="tipo_credito_id.max_financiar")
    monto_minimo_obli = fields.Float("Monto Minimo para aplicar", compute="cal_monto_minimo", store=True)
    balance = fields.Float("Total Pendiente", compute="_get_balance", store=True)
    
    notas = fields.Text("Notas")
    descripcion = fields.Text("Descripción", compute="get_descricion_producto", store=True, readonly=False)
    
    company_id = fields.Many2one("res.company", string="Compañia", default=lambda self:self.env.company)
    tipo_credito_id = fields.Many2one("tipo.credito", string="Tipo de crédito")
    producto_id = fields.Many2one("product.product", string="Producto")
    cuota_id = fields.Many2one("cuotas.credito", string="Cuotas")
    frecuencia_pago = fields.Many2one("frecuencia.credito", string="Plazos de pago")   
    autorizado = fields.Many2one("res.users", string="Autorizado", readonly=True)
    sale_id = fields.Many2one("sale.order", string="Orden de Venta")
    vendedor = fields.Many2one("res.users", string="Vendedor", default=lambda self: self.env.uid, readonly=True)
    cliente_id = fields.Many2one("res.partner",string="Cliente")
    currency_id = fields.Many2one("res.currency",readonly=True,default=lambda self: self.env.user.company_id.currency_id)
    journals_id = fields.Many2one("account.journal",string="Diario",default=lambda self: self.env["account.journal"].search([("name", "=", "Banco")]))

    documentos_ids = fields.One2many("documents.credit", "credito_id", string="Documentos")
    lineas_pagos_ids = fields.One2many("lineas.credito", "credito_id", "Lineas de pago")
    invoices_id = fields.One2many("account.move", "credito_id", string="Facturas")
    payments_ids = fields.One2many("payment.credit", "credit_id", string="Pagos")
    

    # Metodos
    @api.constrains("monto")
    def validation_date(self):
        for rec in self:
            if rec.fecha_primer_pago < rec.fecha:
                raise UserError(
                    _("La fecha del primer pago no puede ser una fecha anterior a la del crédito")
                )
    @api.model
    def create(self, vals):
        if vals.get("numero", ("Nuevo")) == ("Nuevo") and vals["tipo_doc"] == "ven":
            vals["numero"] = self.env["ir.sequence"].next_by_code(
                "credito.financiero"
            ) or ("Nuevo")
            vals["habiliar_solicitud"] = True
        elif vals.get("numero", ("Nuevo")) == ("Nuevo") and vals["tipo_doc"] == "cal":
            vals["numero"] = self.env["ir.sequence"].next_by_code(
                "oferta.credito.financiero"
            ) or ("Nuevo")
            vals["habiliar_solicitud"] = False
        return super(FinancialCredit, self).create(vals)

    #Muestra las cuotas según la frecuencia
    @api.onchange("frecuencia_pago")
    def _get_cuotas(self):
        cuotas = self.frecuencia_pago.mapped("cuotas_ids").mapped("id")
        if cuotas:
            return {"domain": {"cuota_id": [("id", "in", cuotas)]}}

    #Validacion del monto
    @api.onchange("monto_inicial")
    def comprobar_monto(self):
        if not self.monto_inicial >= self.monto_minimo_obli:
            raise UserError(_("El monto inicial es menor al monto minimo requerido"))

    #No permitir borrar documentos ya aceptados
    @api.ondelete(at_uninstall=False)
    def _borrar_credito(self):
        for credito in self:
            if credito.state not in ("borrador", "rechazado"):
                raise UserError(
                    _("No puedes borrar una orden de credito que ya esta confirmada")
                )

    # Estado del Documento
    # Botones
    def reprogramar_cuotas(self):
        return {
            'name': 'Reprogramar Cuotas',
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.reprogramar.cuotas',
            'view_mode': 'form',
            'target': 'new',
        }

    def crear_pago(self):
        action = {
            "name": "Nuevo pago de " + self.cliente_id.name,
            "res_model": "payment.credit",
            "type": "ir.actions.act_window",
            "domain": [("credit_id", "=", self.id)],
            "view_mode": "form",
        }
        action["context"] = {
            "search_default_credit_id": self.id,
            "default_credit_id": self.id,
            "default_type_doc":"pago_credi",
            "default_telefono":self.telefono,
            "default_cliente_id":self.cliente_id.id,
            "default_number":"Borrador"
        }
        return action
    
    def ver_pagos(self):    
        action = {
            "name": "Pagos de " + self.cliente_id.name,
            "res_model": "payment.credit",
            "type": "ir.actions.act_window",
            "domain": [("credit_id", "=", self.id)],
            "view_mode": "tree,form",
        }

        action["context"] = {
            "search_credit_id": self.id,
            "default_credit_id": self.id,
        }

        action["domain"] = [("credit_id", "=", self.id)]
        documentos = self.mapped("payments_ids")
        if len(documentos) == 1:
            action["view_mode"] = "form"
            action["res_id"] = documentos.id
        return action
    
    def ver_facturas(self):
        nombre = self.numero
        search_view_ref = self.env.ref("account.view_account_invoice_filter", False)
        form_view_ref = self.env.ref("account.view_move_form", False)
        tree_view_ref = self.env.ref("account.view_move_tree", False)
        return {
            "domain": [("credito_id", "=", self.id)],
            "name": "Facturas de " + nombre,
            "res_model": "account.move",
            "type": "ir.actions.act_window",
            "views": [(tree_view_ref.id, "tree"), (form_view_ref.id, "form")],
            "search_view_id": search_view_ref and [search_view_ref.id],
        }

    def action_solicitud(self):
        for record in self:
            self.ensure_one()
            template_id = self.env['mail.template'].search([('name', '=', 'Cŕedito: Solicitar Crédito')]).id
            
            ctx = {
                'default_model': 'financial.credit',
                'default_res_id': self.ids[0],
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'force_email': True,
            }
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(False, 'form')],
                'view_id': False,
                'target': 'new',
                'context': ctx,
            }
    
    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('mark_so_as_sent'):
            self.state = "solicitud"
            self.habiliar_solicitud = False
        return super(FinancialCredit, self.with_context(mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)

    def action_aprobado(self):
        for record in self:
            #TODO: Enviar un correo de notificacion en esta funcion
            record.autorizado = self.env.uid
            sale = self.env["sale.order"].search([("credito_id", "=", record.id)])
            sale_order_line = self.env["sale.order.line"].search(
                [("order_id", "=", sale.id)]
            )
            flujo = self.env['ir.config_parameter'].sudo().get_param('financial_credit.flujo_credito')
            if  flujo == "confirm_albaran":
                if record.producto_id.detailed_type == "product":
                    record.state = "aprobado"
                    sale.action_confirm()
                    picking = sale.picking_ids
                    picking.action_assign()
                    picking.move_ids_without_package.mapped("move_line_ids").write(
                        {"qty_done": 1, "lot_id": sale_order_line.lot_id.id}
                    )
                    picking.button_validate()
                else:
                    record.state = "aprobado"
                    sale.action_confirm()

            elif flujo == "confirm_sale":
                record.state = "aprobado"
                sale.action_confirm()
            
            else:
                record.state = "aprobado"
    
    def action_rechazar(self):
        for record in self:
            # TODO: Enviar un correo de notificacion de rechazo del crédito
            record.state = "rechazado"

    def action_reestablecer(self):
        for record in self:
            record.state = "borrador"
            record.habiliar_solicitud = True
    
    def action_cancelar(self):
        for record in self:
            record.state = 'cancelar'

    def action_generate_table(self):
        for record in self:
            if record.tipo_amortiazacion == "lineal":
                self.env["lineas.credito"].search([('credito_id', '=', record.id)]).unlink()
                datos = amortizacion_lineal(record.frecuencia_pago.tipo_frecuencia, record.total,record.cuota_id.numero, record.interes_mensual, record.fecha_primer_pago)
                numero = 1
                res = []
                for dato in datos['tabla']:
                    lineas = {
                        "credito_id":record.id,
                        "numero":numero,
                        "contacto":record.cliente_id.id,
                        "cuota_inicial":dato.get('capital_vivo'),
                        "cuota_fija":dato.get('cuota'),
                        "interes":dato.get('interes'),
                        "capital":dato.get('capital'),
                        "fecha_pago":dato.get('fecha'),
                        "deuda_acum":dato.get('cuota'),
                        "capital_acum": dato.get('capital'),
                        "interes_acum":dato.get('interes'),
                        "payment_state":"pendiente" if record.tipo_doc == 'ven' else ""
                    }
                    add = self.env["lineas.credito"].create(lineas)
                    res.append(add.id)
                    numero += 1
                record.lineas_pagos_ids=[(6,0,res)]

    def action_factura(self):
        for record in self:
            # Factura para el capital desde la orden de venta
            fecha = self.env['lineas.credito'].search([("credito_id", "=", record.id)]).mapped("fecha_pago")
            invoice_capital = self.env["account.move"].create(
                {
                    "credito_id": record.id,
                    "partner_id": record.cliente_id.id,
                    "move_type": "out_invoice",
                    "payment_reference": record.numero + "(Capital)",
                    "invoice_date_due":fecha[-1],
                    "invoice_line_ids": [
                        (
                            0,
                            None,
                            {
                                "product_id": record.producto_id.id,
                                "quantity": 1,
                                "price_unit": record.total,
                            },
                        )
                    ],
                }
            )
            invoice_capital.action_post()

            # Factura de interes
            invoice_interes = self.env["account.move"].create(
                {
                    "credito_id": record.id,
                    "partner_id": record.cliente_id.id,
                    "move_type": "out_invoice",
                    "payment_reference": record.numero + "(Interes)",
                    "invoice_date_due":fecha[-1],
                    "invoice_line_ids": [
                        (
                            0,
                            None,
                            {
                                "product_id": self.env["product.product"].search([("default_code", "=", "INT_CF")]).id,
                                "quantity": 1,
                                "price_unit": record.total_interes
                            },
                        )
                    ],
                }
            )
            invoice_interes.action_post()

            # Registrar pago
            if record.monto_inicial > 0:
                # Datos del pago
                vals = {
                    "reconciled_invoice_ids": [(4, invoice_capital.id)],
                    "partner_id": record.cliente_id.id,
                    "amount": record.monto_inicial,
                    "date": record.fecha,
                    "journal_id": record.journals_id.id,
                    "payment_type": "inbound",
                    "ref": record.numero + " (Monto inicial)",
                }
                self.payment_register(vals, invoice_capital)

            record.state = "pendiente"

    # Calculos
    def _get_balance(self):
        for record in self:
            invoice_capital = self.env["account.move"].search([
                ("credito_id", "=", record.id),
                ("payment_reference", "=", record.numero + "(Capital)")
            ])
            invoice_interes = self.env["account.move"].search([
                ("credito_id", "=", record.id),
                ("payment_reference", "=", record.numero + "(Interes)"),
            ])
            record.balance = (invoice_capital.amount_residual + invoice_interes.amount_residual)

    def _get_url_base_model_str(self):
        action = self.env.ref("financial_credit.menu_action_financial_credit").id
        menu = self.env.ref("financial_credit.menu_financial_credit_root").id
        return "&menu_id="+str(menu)+"cids=1&action="+str(action)+"&model=financial.credit&view_type=form"

    def verificar_documentos(self):
        for record in self:
            docs = self.env['documents.credit'].search([('credito_id', '=', record.id)])
            if docs:
                record.documentos = True
            else: 
                record.documentos = False

    @api.depends("interes_mensual","tipo_amortiazacion", "total","cuota_id")
    def cal_total_interes(self):
        for record in self:
            interes = 0.0
            if record.tipo_amortiazacion == "lineal":
                if record.frecuencia_pago.tipo_frecuencia == "meses":
                    interes = record.interes_mensual * record.cuota_id.numero
                elif record.frecuencia_pago.tipo_frecuencia == "quincenas":
                    interes = (record.interes_mensual / 2) * record.cuota_id.numero
                else:
                    interes = (record.interes_mensual / 4) * record.cuota_id.numero
                record.total_interes = float(Decimal(str(record.total)) * Decimal(str(interes)))

    @api.depends("tipo_amortiazacion","deuda_total","cuota_id")
    def cal_cuota_fija(self):
        for record in self:
            if record.tipo_amortiazacion =="lineal":
                if record.deuda_total > 0 and record.cuota_id:
                    record.cuota_fija = record.deuda_total / record.cuota_id.numero
                else:
                    record.cuota_fija = 0
            else:
                pass

    @api.depends("tipo_amortiazacion","producto_id", "monto")
    def _get_precio(self):
        for record in self:
            if record.tipo_amortiazacion =="lineal":
                if record.venta_servicio:
                    record.precio = record.monto
                else:
                    record.precio = record.producto_id.list_prince
            else:
                pass

    @api.depends("monto", "monto_inicial")
    def cal_total(self):
        for record in self:
            record.total = record.monto - record.monto_inicial

    @api.depends("tipo_amortiazacion","total", "total_interes")
    def cal_deuda_total(self):
        for record in self:
            if record.tipo_amortiazacion =="lineal":
                record.deuda_total = float(Decimal(str(record.total_interes)) + Decimal(str(record.total)))
            else:
                pass
    
    @api.depends("producto_id")
    def cal_venta_servicio(self):
        for record in self:
            if record.producto_id.detailed_type == "product":
                record.venta_servicio = False
            else:
                record.venta_servicio = True

    def numero_pagos_pend(self):
        for record in self:
            lineas_credito = self.env["lineas.credito"].search(
                [("credito_id", "=", record.id)]
            )
            pagos_pend = lineas_credito.filtered(
                lambda p: p.payment_state in ("pendiente", "pago_par", "retrasado")
            )
            record.numero_pagos = len(pagos_pend)

    def cantidad_factura(self):
        for record in self:
            record.numero_facturas = len(
                self.env["account.move"].search([("credito_id", "=", record.id)])
            )

    @api.depends("sale_id")
    def get_descricion_producto(self):
        for record in self:
            record.descripcion = record.sale_id.order_line.name if record.tipo_doc == "ven" else "Escriba una descripcion sobre este credito..."
    
    @api.depends("tipo_credito_id", "precio")
    def cal_monto_minimo(self):
        for record in self:
            record.monto_minimo_obli = record.precio - (record.precio * record.tipo_credito_id.max_financiar)
            record.monto_inicial = record.monto_minimo_obli
    

    # Funcion para registrar pagos
    @api.model
    def payment_register(self, vals: dict, invoice):
        """
        Registra un pago y la concilia a una factura
        :param vals: es un diccionario que contiene los datos del pago
        :param invoice: factura la cual se hará la conciliación
        :returns: la conciliacion
        """
        payment = self.env["account.payment"].create(vals)
        payment.action_post()
        inv_receivable = invoice.line_ids.filtered(
            lambda l: l.account_id.internal_type == "receivable"
        )
        pay_receivable = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.internal_type == "receivable"
        )
        # Conciliar el pago con la factura
        return (inv_receivable + pay_receivable).reconcile()
