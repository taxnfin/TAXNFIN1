"""CONTALink API integration service"""
import httpx
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

CONTALINK_BASE_URL = os.environ.get('CONTALINK_BASE_URL', 'https://794lol2h95.execute-api.us-east-1.amazonaws.com/prod')


class ContalinkClient:
    """Client for CONTALink API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = CONTALINK_BASE_URL
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    async def test_connection(self) -> Dict:
        """Test if the API key is valid by fetching trial balance for current month"""
        try:
            today = datetime.now()
            start = f"{today.year}-{today.month:02d}-01"
            end = f"{today.year}-{today.month:02d}-28"
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(
                    f"{self.base_url}/accounting/trial-balance/",
                    headers=self.headers,
                    params={'start_date': start, 'end_date': end, 'period': 'O'}
                )
                if res.status_code == 200:
                    data = res.json()
                    return {'status': 'connected', 'message': data.get('message', 'OK')}
                return {'status': 'error', 'message': f'HTTP {res.status_code}: {res.text[:200]}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_trial_balance(self, start_date: str, end_date: str, include_period_13: bool = False) -> Dict:
        """Get trial balance (balanza de comprobación)"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(
                    f"{self.base_url}/accounting/trial-balance/",
                    headers=self.headers,
                    params={
                        'start_date': start_date,
                        'end_date': end_date,
                        'period': 'I' if include_period_13 else 'O'
                    }
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            logger.error(f"ContalinkClient.get_trial_balance error: {e}")
            return {'status': 0, 'message': str(e)}
    
    async def get_invoices(self, rfc: str, transaction_type: str, document_type: str, 
                          start_date: str, end_date: str, page: int = 0) -> Dict:
        """Get fiscal documents list"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(
                    f"{self.base_url}/invoices/list/",
                    headers=self.headers,
                    params={
                        'transaction_type': transaction_type,
                        'document_type': document_type,
                        'rfc': rfc,
                        'start_date': start_date,
                        'end_date': end_date,
                        'page': page
                    }
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            logger.error(f"ContalinkClient.get_invoices error: {e}")
            return {'status': 0, 'message': str(e)}
    
    async def get_account_balance(self, account_number: str, date: str) -> Dict:
        """Get balance of a specific account"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(
                    f"{self.base_url}/accounting/get-account-balance/{account_number}/",
                    headers=self.headers,
                    params={'date': date, 'period': 'O'}
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            return {'status': 0, 'message': str(e)}
    
    async def create_conciliation(self, invoice_uuid: str, amount: float, 
                                  bank_account: str, payment_date: str, payment_form: str = '03') -> Dict:
        """Create a conciliation for an invoice"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.post(
                    f"{self.base_url}/conciliation/create/",
                    headers=self.headers,
                    json={
                        'invoice_id': invoice_uuid,
                        'amount': amount,
                        'bank_account': bank_account,
                        'payment_date': payment_date,
                        'payment_form': payment_form
                    }
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            return {'status': 0, 'message': str(e)}
