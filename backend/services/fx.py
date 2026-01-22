"""FX Rate service"""
from datetime import datetime, timezone

from core.database import db


async def get_fx_rate_by_date(company_id: str, moneda: str, fecha: datetime = None) -> float:
    """Get the exchange rate for a specific currency and date.
    If no rate exists for that date, returns the closest previous rate.
    """
    if moneda == 'MXN':
        return 1.0
    
    # Default rates
    default_rates = {'USD': 17.50, 'EUR': 19.00, 'GBP': 23.00, 'CAD': 13.00, 'CHF': 22.00, 'CNY': 2.50, 'JPY': 0.12}
    
    if fecha is None:
        fecha = datetime.now(timezone.utc)
    
    # Get the rate for the specified date or closest previous date
    fecha_str = fecha.isoformat() if isinstance(fecha, datetime) else fecha
    
    rate_doc = await db.fx_rates.find_one(
        {
            'company_id': company_id,
            '$or': [
                {'moneda_origen': moneda},
                {'moneda_cotizada': moneda}
            ],
            'fecha_vigencia': {'$lte': fecha_str}
        },
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    
    if rate_doc:
        return rate_doc.get('tasa') or rate_doc.get('tipo_cambio') or default_rates.get(moneda, 1.0)
    
    # No historical rate found, try to get any rate for this currency
    any_rate = await db.fx_rates.find_one(
        {
            'company_id': company_id,
            '$or': [
                {'moneda_origen': moneda},
                {'moneda_cotizada': moneda}
            ]
        },
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    
    if any_rate:
        return any_rate.get('tasa') or any_rate.get('tipo_cambio') or default_rates.get(moneda, 1.0)
    
    return default_rates.get(moneda, 1.0)
