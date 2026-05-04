"""
Forex Service - Wrapper around Banxico FX rates with fallback to OpenExchange
"""
import os
import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Fallback rates if all APIs fail
FALLBACK_RATES = {
    'USD': 17.50,
    'EUR': 19.00,
    'GBP': 23.00,
    'CAD': 13.00,
    'CHF': 23.50,
    'JPY': 0.14,
    'CNY': 2.85,
}

# Banxico SIE series IDs
BANXICO_SERIES = {
    'USD': 'SF43718',
    'EUR': 'SF46410',
    'GBP': 'SF46406',
    'CAD': 'SF60634',
}

BANXICO_BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"


class ForexService:
    def __init__(self):
        self.banxico_token = os.environ.get('BANXICO_TOKEN') or os.environ.get('BANXICO_API_TOKEN')
        self.openexchange_key = os.environ.get('OPENEXCHANGE_APP_ID') or os.environ.get('OPEN_EXCHANGE_APP_ID')

    async def _fetch_banxico_rate(self, currency: str) -> Optional[float]:
        """Fetch latest rate from Banxico SIE API"""
        if not self.banxico_token or currency not in BANXICO_SERIES:
            return None
        series_id = BANXICO_SERIES[currency]
        url = f"{BANXICO_BASE}/series/{series_id}/datos/oportuno"
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                r = await client.get(url, params={'token': self.banxico_token},
                                     headers={'Accept': 'application/json'})
                if r.status_code != 200:
                    logger.warning(f"Banxico {currency}: HTTP {r.status_code}")
                    return None
                data = r.json()
                series_data = data.get('bmx', {}).get('series', [])
                if not series_data:
                    return None
                datos = series_data[0].get('datos', [])
                for entry in reversed(datos):
                    value = entry.get('dato')
                    if value and value not in ('N/E', 'N/A'):
                        try:
                            return float(value)
                        except ValueError:
                            continue
        except Exception as e:
            logger.warning(f"Banxico {currency} error: {e}")
        return None

    async def _fetch_openexchange_rates(self) -> Dict[str, float]:
        """Fetch rates from OpenExchangeRates (MXN base via USD pivot)"""
        if not self.openexchange_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    'https://openexchangerates.org/api/latest.json',
                    params={'app_id': self.openexchange_key, 'base': 'USD'}
                )
                if r.status_code != 200:
                    return {}
                data = r.json()
                rates_usd = data.get('rates', {})
                mxn_per_usd = rates_usd.get('MXN', 17.5)
                # Convert all to MXN base
                result = {}
                for currency in FALLBACK_RATES:
                    if currency == 'USD':
                        result['USD'] = mxn_per_usd
                    elif currency in rates_usd and rates_usd[currency] > 0:
                        result[currency] = mxn_per_usd / rates_usd[currency]
                return result
        except Exception as e:
            logger.warning(f"OpenExchange error: {e}")
        return {}

    async def get_all_rates(self) -> Dict[str, dict]:
        """
        Fetch all FX rates. Tries Banxico first, then OpenExchange, then fallback.
        Returns dict: { 'USD': {'rate': 17.5, 'source': 'banxico'}, ... }
        """
        # Try OpenExchange first (covers more currencies)
        oe_rates = await self._fetch_openexchange_rates()

        result = {}
        for currency, fallback in FALLBACK_RATES.items():
            # Try Banxico for major currencies
            banxico_rate = await self._fetch_banxico_rate(currency)
            if banxico_rate and banxico_rate > 0:
                result[currency] = {'rate': banxico_rate, 'source': 'banxico'}
            elif currency in oe_rates and oe_rates[currency] > 0:
                result[currency] = {'rate': oe_rates[currency], 'source': 'openexchange'}
            else:
                result[currency] = {'rate': fallback, 'source': 'fallback'}
                logger.warning(f"Using fallback rate for {currency}: {fallback}")

        return result


# Singleton
_service_instance: Optional[ForexService] = None


def get_forex_service() -> ForexService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ForexService()
    return _service_instance
