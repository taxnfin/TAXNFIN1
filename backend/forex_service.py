"""
Forex Service - Real-time exchange rates from Banxico and Open Exchange Rates
Provides official MXN exchange rates for enterprise financial applications
"""
import os
import httpx
from datetime import datetime, timezone
from typing import Dict, Optional
import asyncio

# API Tokens from environment
BANXICO_TOKEN = os.environ.get('BANXICO_TOKEN', '')
OPENEXCHANGE_APP_ID = os.environ.get('OPENEXCHANGE_APP_ID', '')

# Banxico Series IDs for exchange rates (MXN per foreign currency)
BANXICO_SERIES = {
    'USD': 'SF43718',  # Dólar USA (FIX)
    'EUR': 'SF46410',  # Euro
    'GBP': 'SF46407',  # Libra Esterlina
    'JPY': 'SF46406',  # Yen Japonés
    'CAD': 'SF60632',  # Dólar Canadiense
}

# Currencies to fetch from Open Exchange Rates (not available in Banxico)
OPENEXCHANGE_CURRENCIES = ['CHF', 'CNY']

# Fallback rates in case APIs are unavailable
FALLBACK_RATES = {
    'USD': 20.50,
    'EUR': 22.00,
    'GBP': 26.00,
    'JPY': 0.14,
    'CHF': 23.50,
    'CAD': 15.00,
    'CNY': 2.85,
}


class ForexService:
    """Service to fetch real-time exchange rates from Banxico and Open Exchange Rates"""
    
    def __init__(self, banxico_token: str = None, openexchange_app_id: str = None):
        self.banxico_token = banxico_token or BANXICO_TOKEN
        self.openexchange_app_id = openexchange_app_id or OPENEXCHANGE_APP_ID
        self.banxico_base_url = "https://www.banxico.org.mx/SieAPIRest/service/v1"
        self.openexchange_base_url = "https://openexchangerates.org/api"
    
    async def fetch_banxico_rates(self) -> Dict[str, float]:
        """
        Fetch exchange rates from Banxico API
        Returns dict of currency -> MXN rate (pesos per foreign currency unit)
        """
        if not self.banxico_token:
            print("Warning: BANXICO_TOKEN not configured, using fallback rates")
            return {}
        
        rates = {}
        series_ids = ','.join(BANXICO_SERIES.values())
        url = f"{self.banxico_base_url}/series/{series_ids}/datos/oportuno"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={'token': self.banxico_token},
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    series_data = data.get('bmx', {}).get('series', [])
                    
                    # Map series IDs back to currency codes
                    series_to_currency = {v: k for k, v in BANXICO_SERIES.items()}
                    
                    for serie in series_data:
                        serie_id = serie.get('idSerie', '')
                        currency = series_to_currency.get(serie_id)
                        if currency:
                            datos = serie.get('datos', [])
                            if datos:
                                # Get most recent rate
                                latest = datos[-1]
                                try:
                                    rate_str = latest.get('dato', '0').replace(',', '')
                                    rate = float(rate_str)
                                    if rate > 0:
                                        rates[currency] = rate
                                        print(f"Banxico {currency}: {rate} MXN (fecha: {latest.get('fecha')})")
                                except (ValueError, TypeError) as e:
                                    print(f"Error parsing Banxico rate for {currency}: {e}")
                else:
                    print(f"Banxico API error: {response.status_code} - {response.text[:200]}")
                    
        except Exception as e:
            print(f"Error fetching Banxico rates: {e}")
        
        return rates
    
    async def fetch_openexchange_rates(self) -> Dict[str, float]:
        """
        Fetch exchange rates from Open Exchange Rates API
        Converts USD-based rates to MXN-based rates
        Returns dict of currency -> MXN rate
        """
        if not self.openexchange_app_id:
            print("Warning: OPENEXCHANGE_APP_ID not configured, using fallback rates")
            return {}
        
        rates = {}
        url = f"{self.openexchange_base_url}/latest.json"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={
                        'app_id': self.openexchange_app_id,
                        'symbols': 'MXN,CHF,CNY'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    usd_rates = data.get('rates', {})
                    
                    # Get MXN per USD rate
                    mxn_per_usd = usd_rates.get('MXN', 20.50)
                    
                    # Convert to MXN per foreign currency
                    for currency in OPENEXCHANGE_CURRENCIES:
                        if currency in usd_rates:
                            # rate is USD per foreign currency
                            usd_per_foreign = usd_rates[currency]
                            if usd_per_foreign > 0:
                                # MXN per foreign = (MXN per USD) / (USD per foreign)
                                mxn_per_foreign = mxn_per_usd / usd_per_foreign
                                rates[currency] = round(mxn_per_foreign, 4)
                                print(f"OpenExchange {currency}: {rates[currency]} MXN")
                else:
                    print(f"OpenExchange API error: {response.status_code} - {response.text[:200]}")
                    
        except Exception as e:
            print(f"Error fetching OpenExchange rates: {e}")
        
        return rates
    
    async def get_all_rates(self) -> Dict[str, dict]:
        """
        Fetch all exchange rates from both APIs
        Returns dict with rate info including source and timestamp
        """
        # Fetch from both APIs concurrently
        banxico_task = self.fetch_banxico_rates()
        openexchange_task = self.fetch_openexchange_rates()
        
        banxico_rates, openexchange_rates = await asyncio.gather(
            banxico_task, openexchange_task
        )
        
        # Combine results with metadata
        all_rates = {'MXN': {'rate': 1.0, 'source': 'base', 'updated_at': datetime.now(timezone.utc).isoformat()}}
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Add Banxico rates (official)
        for currency, rate in banxico_rates.items():
            all_rates[currency] = {
                'rate': rate,
                'source': 'banxico',
                'updated_at': timestamp
            }
        
        # Add OpenExchange rates
        for currency, rate in openexchange_rates.items():
            all_rates[currency] = {
                'rate': rate,
                'source': 'openexchange',
                'updated_at': timestamp
            }
        
        # Fill in fallback rates for any missing currencies
        for currency, fallback_rate in FALLBACK_RATES.items():
            if currency not in all_rates:
                all_rates[currency] = {
                    'rate': fallback_rate,
                    'source': 'fallback',
                    'updated_at': timestamp
                }
                print(f"Using fallback rate for {currency}: {fallback_rate}")
        
        return all_rates
    
    async def get_simple_rates(self) -> Dict[str, float]:
        """
        Get simple rate dictionary (currency -> MXN rate)
        For backward compatibility with existing code
        """
        all_rates = await self.get_all_rates()
        return {currency: info['rate'] for currency, info in all_rates.items()}


# Singleton instance
_forex_service: Optional[ForexService] = None

def get_forex_service() -> ForexService:
    """Get or create forex service instance"""
    global _forex_service
    if _forex_service is None:
        _forex_service = ForexService()
    return _forex_service


async def update_fx_rates_in_db(db, company_id: str) -> Dict[str, dict]:
    """
    Update FX rates in database for a company
    Fetches real-time rates and stores them
    """
    service = get_forex_service()
    rates = await service.get_all_rates()
    
    timestamp = datetime.now(timezone.utc)
    
    for currency, rate_info in rates.items():
        if currency == 'MXN':
            continue  # Skip base currency
        
        # Check if rate already exists for today
        existing = await db.fx_rates.find_one({
            'company_id': company_id,
            'moneda_origen': currency,
            'moneda_destino': 'MXN',
            'fecha_vigencia': {'$gte': timestamp.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()}
        })
        
        if existing:
            # Update existing rate
            await db.fx_rates.update_one(
                {'_id': existing['_id']},
                {'$set': {
                    'tasa': rate_info['rate'],
                    'fuente': rate_info['source'],
                    'updated_at': timestamp.isoformat()
                }}
            )
        else:
            # Insert new rate
            import uuid
            await db.fx_rates.insert_one({
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'moneda_origen': currency,
                'moneda_destino': 'MXN',
                'tasa': rate_info['rate'],
                'fuente': rate_info['source'],
                'fecha_vigencia': timestamp.isoformat(),
                'created_at': timestamp.isoformat(),
                'updated_at': timestamp.isoformat()
            })
    
    return rates
