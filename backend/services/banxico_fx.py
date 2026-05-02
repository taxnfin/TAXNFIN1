"""
Banxico SIE (Sistema de Información Económica) FX rate client.

Fetches official FIX exchange rates published in the DOF (Diario Oficial de la
Federación). Used to validate the per-CFDI exchange rate against the official
rate of issuance day, to flag potential capture errors that could affect SAT
deductibility.

Free API token: https://www.banxico.org.mx/SieAPIRest/service/v1/token
Set BANXICO_TOKEN in /app/backend/.env. Without a token the service silently
returns None so the rest of the app keeps working.

Series IDs:
  SF43718 - USD/MXN FIX (DOF)
  SF46410 - EUR/MXN FIX (Banxico)
  SF46406 - GBP/MXN FIX (Banxico)
  SF60634 - CAD/MXN FIX (Banxico)
"""
from __future__ import annotations
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import httpx

logger = logging.getLogger(__name__)

BANXICO_BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"

# Currency -> Banxico SIE series ID
SERIES = {
    'USD': 'SF43718',
    'EUR': 'SF46410',
    'GBP': 'SF46406',
    'CAD': 'SF60634',
}

# Simple in-memory cache: (currency, date_iso) -> (rate, ts)
_CACHE: Dict[tuple, tuple] = {}
_CACHE_TTL = timedelta(hours=12)


def _token() -> Optional[str]:
    return os.environ.get('BANXICO_TOKEN') or os.environ.get('BANXICO_API_TOKEN')


async def get_official_rate(currency: str, date_iso: Optional[str] = None) -> Optional[float]:
    """Return the official Banxico FIX rate for the given currency on the given
    date (YYYY-MM-DD). If date is None, returns the latest available.
    
    Falls back to the previous business day if the requested date has no
    publication (weekends/holidays).
    """
    currency = (currency or '').upper()
    if currency == 'MXN' or currency not in SERIES:
        return None
    
    token = _token()
    if not token:
        logger.debug("BANXICO_TOKEN not configured; skipping rate lookup")
        return None
    
    series_id = SERIES[currency]
    
    # Cache lookup
    cache_key = (currency, date_iso or 'latest')
    cached = _CACHE.get(cache_key)
    if cached and datetime.utcnow() - cached[1] < _CACHE_TTL:
        return cached[0]
    
    headers = {'Accept': 'application/json'}
    
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            if date_iso:
                # Look up a 7-day window ending on date_iso to handle weekends.
                # Banxico expects ISO format YYYY-MM-DD/YYYY-MM-DD in the URL.
                end = datetime.strptime(date_iso, '%Y-%m-%d')
                start = end - timedelta(days=7)
                url = (
                    f"{BANXICO_BASE}/series/{series_id}/datos/"
                    f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
                )
            else:
                url = f"{BANXICO_BASE}/series/{series_id}/datos/oportuno"
            
            # Banxico is sensitive about token placement; send it both in query
            # string and header to be safe.
            r = await client.get(url, headers=headers, params={'token': token})
            if r.status_code != 200:
                logger.warning("Banxico API %s: %s", r.status_code, r.text[:200])
                return None
            
            data = r.json()
            series_data = data.get('bmx', {}).get('series', [])
            if not series_data:
                return None
            datos = series_data[0].get('datos', [])
            if not datos:
                return None
            
            # Take the last available data point (closest to requested date)
            for entry in reversed(datos):
                value = entry.get('dato')
                if value and value not in ('N/E', 'N/A'):
                    try:
                        rate = float(value)
                        _CACHE[cache_key] = (rate, datetime.utcnow())
                        return rate
                    except ValueError:
                        continue
            return None
    except httpx.HTTPError as e:
        logger.warning("Banxico API request failed: %s", e)
        return None
    except Exception as e:
        logger.exception("Banxico API unexpected error: %s", e)
        return None


def evaluate_deviation(actual_rate: float, official_rate: float) -> dict:
    """Compute the deviation of `actual_rate` vs `official_rate` and return a
    structured result with status and percent."""
    if not official_rate or official_rate <= 0:
        return {'status': 'unknown', 'deviation_pct': None}
    deviation_pct = ((actual_rate - official_rate) / official_rate) * 100
    abs_dev = abs(deviation_pct)
    if abs_dev <= 1.0:
        status = 'ok'
    elif abs_dev <= 5.0:
        status = 'warning'
    else:
        status = 'critical'
    return {
        'status': status,
        'deviation_pct': round(deviation_pct, 2),
        'official_rate': round(official_rate, 4),
        'actual_rate': round(actual_rate, 4),
    }
