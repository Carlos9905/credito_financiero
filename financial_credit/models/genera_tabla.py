from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from datetime import datetime

import psycopg2
import logging

_logger = logging.getLogger(__name__)

MENSUAL = 'meses'
QUINCENAL = 'quincenas'
SEMANAL = "semanas"

def amortizacion_compuesta(tipo_frecuencia: str, cv: list, fp: list, n: int, cf, tem):
    pass

def amortizacion_lineal(tipo_frecuencia:str, moto_a_prestar:float, cuotas:int, interes_mensual:float, fecha) -> dict:
    """
    
    Genera la tabla de amortización lineal simple
    :param tipo_frecuencia: Frecuencia de pago (Mensual, Semanal, Quincenal)
    :param moto_a_prestar: Monto el cual se hará el prestamo
    :param cuotas: Cuotas de plazo a pagar
    :param interes_mensual: La tasa de interés mensual a aplicar
    :param fecha: Fecha del primer pago
    :returns: Diccionario con la tabla generada
    
    """
    
    
    if tipo_frecuencia == MENSUAL:
        interes_mensual = interes_mensual
    elif tipo_frecuencia == QUINCENAL:
        interes_mensual = interes_mensual / 2
    else:
        interes_mensual = interes_mensual / 4
    
    
    interes = Decimal(str(interes_mensual)) * cuotas
    total_interes = Decimal(str(moto_a_prestar)) * interes
    total_pagar = total_interes + Decimal(str(moto_a_prestar))
    cuota_fija = total_pagar / cuotas
    interes_fijo = total_interes / cuotas
    capital_fijo = cuota_fija - interes_fijo
    dat = {'datos_principales':{}, 'tabla':[]}
    monto = total_pagar
    #fecha = datetime.today()
    
    
    for i in range(cuotas):
        if tipo_frecuencia == MENSUAL:
            monto -= cuota_fija
            dat['tabla'].append({
                "capital_vivo": float(monto.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "capital": float(capital_fijo.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "interes": float(interes_fijo.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "cuota": float(cuota_fija.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "fecha": fecha
            })
            fecha += relativedelta(months=1)
            
        elif tipo_frecuencia == QUINCENAL:
            monto -= cuota_fija
            dat['tabla'].append({
                "capital_vivo": float(monto.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "capital": float(capital_fijo.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "interes": float(interes_fijo.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "cuota": float(cuota_fija.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "fecha": fecha
            })
            fecha += relativedelta(days=15)
            
        else:
            monto -= cuota_fija
            dat['tabla'].append({
                "capital_vivo": float(monto.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "capital": float(capital_fijo.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "interes": float(interes_fijo.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "cuota": float(cuota_fija.quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)),
                "fecha": fecha
            })
            fecha += relativedelta(weeks=1)
            
    dat['datos_principales'] = {
        'capital_fijo':float(capital_fijo),
        'interes_fijo': float(interes_fijo),
        'total_pagar': float(total_pagar)
    }
    
    
    return dat