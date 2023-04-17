from odoo import models, api, fields
import pytz
from datetime import datetime
from dateutil.relativedelta import relativedelta

class WizardReprogramarCuotas(models.TransientModel):
    _name = "wizard.reprogramar.cuotas"
    _description = "Wizard para reprogramar cuotas"

    fecha = fields.Date("Fecha", default=lambda self: datetime.now(pytz.timezone(self.env.user.tz)), help="Fecha en la que va a empezar los pagos")
    
    def reprogramar(self):
        credito_id = self.env.context.get('active_id')
        lineas = self.env['lineas.credito'].search([("credito_id", "=", credito_id)])
        credito = self.env['financial.credit'].search([('id','=',credito_id)])
        frecuencia = credito.frecuencia_pago.tipo_frecuencia
        num = 1
        
        for i in range(len(lineas)):
            if frecuencia == 'meses':
                query = "UPDATE lineas_credito SET fecha_pago = '"+ str(self.fecha) +"' WHERE credito_id = " + str(credito_id) + " AND numero = "+ str(num)
                self.env.cr.execute(query)
                self.fecha += relativedelta(months=1)
                num += 1
        