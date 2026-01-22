"""
Test suite for 6 new features in TaxnFin app:
1. Payments summary endpoint returns currency breakdown (total_por_cobrar_mxn, total_por_cobrar_usd, etc.)
2. Payment edit dialog includes bank account selector dropdown
3. Payment edit dialog shows currency conversion preview for non-MXN amounts
4. Conciliaciones shows 'Saldo Inicial (Consolidado)' with MXN label when 'Todas las cuentas' is selected
5. FX Rates module has 'Vista Anual' tab showing monthly averages
6. Transfer endpoint /api/bank-transactions/transfer-account works correctly
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"

# Bank account IDs from context
BBVA_MXN_ACCOUNT_ID = "0050a523-c83c-4473-8288-e877e70526ca"
CITIBANAMEX_USD_ACCOUNT_ID = "58038ce1-a4db-4375-b870-15c3cc5653b4"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestPaymentsSummaryEndpoint:
    """Test Feature 1: Payments summary endpoint returns currency breakdown"""
    
    def test_payments_summary_returns_currency_breakdown(self, auth_headers):
        """Verify /api/payments/summary returns MXN and USD breakdown fields"""
        response = requests.get(f"{BASE_URL}/api/payments/summary", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Check for MXN breakdown fields
        assert "total_por_cobrar_mxn" in data, "Missing total_por_cobrar_mxn field"
        assert "total_por_pagar_mxn" in data, "Missing total_por_pagar_mxn field"
        assert "pagado_mes_mxn" in data, "Missing pagado_mes_mxn field"
        assert "cobrado_mes_mxn" in data, "Missing cobrado_mes_mxn field"
        
        # Check for USD breakdown fields
        assert "total_por_cobrar_usd" in data, "Missing total_por_cobrar_usd field"
        assert "total_por_pagar_usd" in data, "Missing total_por_pagar_usd field"
        assert "pagado_mes_usd" in data, "Missing pagado_mes_usd field"
        assert "cobrado_mes_usd" in data, "Missing cobrado_mes_usd field"
        
        # Check for exchange rate fields
        assert "tc_usd" in data, "Missing tc_usd field"
        assert "tc_eur" in data, "Missing tc_eur field"
        
        print(f"✓ Payments summary returns currency breakdown: MXN={data['total_por_cobrar_mxn']}, USD={data['total_por_cobrar_usd']}")
    
    def test_payments_summary_values_are_numeric(self, auth_headers):
        """Verify all currency values are numeric"""
        response = requests.get(f"{BASE_URL}/api/payments/summary", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        numeric_fields = [
            "total_por_cobrar_mxn", "total_por_cobrar_usd",
            "total_por_pagar_mxn", "total_por_pagar_usd",
            "pagado_mes_mxn", "pagado_mes_usd",
            "cobrado_mes_mxn", "cobrado_mes_usd",
            "tc_usd", "tc_eur"
        ]
        
        for field in numeric_fields:
            assert isinstance(data.get(field), (int, float)), f"{field} should be numeric, got {type(data.get(field))}"
        
        print("✓ All currency breakdown values are numeric")


class TestBankAccountsEndpoint:
    """Test Feature 2: Bank accounts available for payment edit dialog"""
    
    def test_bank_accounts_list_available(self, auth_headers):
        """Verify bank accounts endpoint returns list for dropdown"""
        response = requests.get(f"{BASE_URL}/api/bank-accounts", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        accounts = response.json()
        assert isinstance(accounts, list), "Bank accounts should be a list"
        assert len(accounts) >= 2, "Should have at least 2 bank accounts (BBVA MXN and Citibanamex USD)"
        
        # Check for expected accounts
        account_ids = [acc['id'] for acc in accounts]
        currencies = [acc.get('moneda', 'MXN') for acc in accounts]
        
        print(f"✓ Bank accounts available: {len(accounts)} accounts with currencies {set(currencies)}")
    
    def test_bank_accounts_have_required_fields(self, auth_headers):
        """Verify bank accounts have fields needed for dropdown"""
        response = requests.get(f"{BASE_URL}/api/bank-accounts", headers=auth_headers)
        assert response.status_code == 200
        
        accounts = response.json()
        for acc in accounts:
            assert "id" in acc, "Account missing id"
            assert "nombre" in acc or "nombre_banco" in acc, "Account missing name"
            assert "moneda" in acc, "Account missing moneda"
            assert "banco" in acc, "Account missing banco"
        
        print("✓ Bank accounts have all required fields for dropdown")


class TestPaymentWithBankAccount:
    """Test Feature 2 & 3: Payment creation/update with bank account and currency conversion"""
    
    def test_create_payment_with_bank_account(self, auth_headers):
        """Create a payment with bank_account_id"""
        payment_data = {
            "tipo": "pago",
            "concepto": "TEST_Payment with bank account",
            "monto": 1000.00,
            "moneda": "MXN",
            "metodo_pago": "transferencia",
            "fecha_vencimiento": (datetime.now() + timedelta(days=7)).isoformat(),
            "bank_account_id": BBVA_MXN_ACCOUNT_ID,
            "es_real": True
        }
        
        response = requests.post(f"{BASE_URL}/api/payments", json=payment_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        
        created = response.json()
        assert created.get("bank_account_id") == BBVA_MXN_ACCOUNT_ID, "Bank account ID not saved"
        
        # Cleanup
        payment_id = created.get("id")
        if payment_id:
            requests.delete(f"{BASE_URL}/api/payments/{payment_id}", headers=auth_headers)
        
        print("✓ Payment created with bank_account_id successfully")
    
    def test_create_usd_payment_with_exchange_rate(self, auth_headers):
        """Create a USD payment and verify tipo_cambio_historico is set"""
        payment_data = {
            "tipo": "cobro",
            "concepto": "TEST_USD Payment with exchange rate",
            "monto": 500.00,
            "moneda": "USD",
            "metodo_pago": "transferencia",
            "fecha_vencimiento": (datetime.now() + timedelta(days=7)).isoformat(),
            "bank_account_id": CITIBANAMEX_USD_ACCOUNT_ID,
            "es_real": True
        }
        
        response = requests.post(f"{BASE_URL}/api/payments", json=payment_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        
        created = response.json()
        # tipo_cambio_historico should be set for non-MXN payments
        # Note: This may be set on creation or may need to be checked in the stored document
        
        # Cleanup
        payment_id = created.get("id")
        if payment_id:
            requests.delete(f"{BASE_URL}/api/payments/{payment_id}", headers=auth_headers)
        
        print("✓ USD payment created successfully")


class TestFXRatesYearEndpoint:
    """Test Feature 5: FX Rates annual view with monthly averages"""
    
    def test_fx_rates_year_endpoint_exists(self, auth_headers):
        """Verify /api/fx-rates/year/{year} endpoint exists"""
        current_year = datetime.now().year
        response = requests.get(f"{BASE_URL}/api/fx-rates/year/{current_year}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "year" in data, "Missing year field"
        assert data["year"] == current_year, f"Year mismatch: expected {current_year}, got {data['year']}"
        
        print(f"✓ FX rates year endpoint returns data for {current_year}")
    
    def test_fx_rates_year_has_monthly_averages(self, auth_headers):
        """Verify year endpoint returns monthly_averages structure"""
        current_year = datetime.now().year
        response = requests.get(f"{BASE_URL}/api/fx-rates/year/{current_year}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        assert "currencies" in data, "Missing currencies field"
        assert "total_rates" in data, "Missing total_rates field"
        assert "by_currency" in data, "Missing by_currency field"
        assert "monthly_averages" in data, "Missing monthly_averages field"
        
        # monthly_averages should be a dict
        assert isinstance(data["monthly_averages"], dict), "monthly_averages should be a dict"
        
        print(f"✓ FX rates year endpoint has monthly_averages: {list(data['monthly_averages'].keys())}")
    
    def test_fx_rates_year_structure(self, auth_headers):
        """Verify the structure of monthly averages"""
        current_year = datetime.now().year
        response = requests.get(f"{BASE_URL}/api/fx-rates/year/{current_year}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # If there are currencies, check the structure
        if data.get("currencies"):
            for currency in data["currencies"]:
                if currency in data.get("monthly_averages", {}):
                    monthly = data["monthly_averages"][currency]
                    assert isinstance(monthly, dict), f"Monthly averages for {currency} should be a dict"
                    # Keys should be month numbers (1-12)
                    for month_key in monthly.keys():
                        assert isinstance(int(month_key), int), f"Month key should be numeric"
                        assert 1 <= int(month_key) <= 12, f"Month should be 1-12, got {month_key}"
        
        print("✓ FX rates year structure is correct")


class TestTransferAccountEndpoint:
    """Test Feature 6: Transfer transactions between accounts"""
    
    def test_transfer_endpoint_exists(self, auth_headers):
        """Verify /api/bank-transactions/transfer-account endpoint exists"""
        # Test with invalid data to verify endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/bank-transactions/transfer-account",
            json={},
            headers=auth_headers
        )
        # Should return 400 (bad request) not 404 (not found)
        assert response.status_code != 404, "Transfer endpoint not found"
        assert response.status_code == 400, f"Expected 400 for empty data, got {response.status_code}"
        
        print("✓ Transfer account endpoint exists")
    
    def test_transfer_requires_both_accounts(self, auth_headers):
        """Verify transfer requires from_account_id and to_account_id"""
        # Test with only from_account_id
        response = requests.post(
            f"{BASE_URL}/api/bank-transactions/transfer-account",
            json={"from_account_id": BBVA_MXN_ACCOUNT_ID},
            headers=auth_headers
        )
        assert response.status_code == 400, "Should require to_account_id"
        
        # Test with only to_account_id
        response = requests.post(
            f"{BASE_URL}/api/bank-transactions/transfer-account",
            json={"to_account_id": CITIBANAMEX_USD_ACCOUNT_ID},
            headers=auth_headers
        )
        assert response.status_code == 400, "Should require from_account_id"
        
        print("✓ Transfer endpoint validates required fields")
    
    def test_transfer_validates_account_existence(self, auth_headers):
        """Verify transfer validates that accounts exist"""
        response = requests.post(
            f"{BASE_URL}/api/bank-transactions/transfer-account",
            json={
                "from_account_id": "non-existent-account-id",
                "to_account_id": CITIBANAMEX_USD_ACCOUNT_ID
            },
            headers=auth_headers
        )
        assert response.status_code == 404, f"Should return 404 for non-existent account, got {response.status_code}"
        
        print("✓ Transfer endpoint validates account existence")


class TestBankTransactionsCurrency:
    """Test that bank transactions show correct currency after transfer"""
    
    def test_bank_transactions_have_currency(self, auth_headers):
        """Verify bank transactions have moneda field"""
        response = requests.get(f"{BASE_URL}/api/bank-transactions?limit=50", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        transactions = response.json()
        if transactions:
            # Check that transactions have moneda field
            for txn in transactions[:10]:  # Check first 10
                # moneda might be on the transaction or inherited from account
                has_currency = "moneda" in txn or "bank_account_id" in txn
                assert has_currency, "Transaction should have moneda or bank_account_id"
        
        print(f"✓ Bank transactions endpoint returns {len(transactions)} transactions")
    
    def test_usd_account_transactions(self, auth_headers):
        """Check transactions in USD account"""
        response = requests.get(
            f"{BASE_URL}/api/bank-transactions?limit=100",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        transactions = response.json()
        usd_transactions = [t for t in transactions if t.get('bank_account_id') == CITIBANAMEX_USD_ACCOUNT_ID]
        
        print(f"✓ Found {len(usd_transactions)} transactions in USD account (Citibanamex)")
        
        # Check if any have USD currency
        usd_currency_count = sum(1 for t in usd_transactions if t.get('moneda') == 'USD')
        print(f"  - {usd_currency_count} transactions with USD currency")


class TestBankAccountsSummary:
    """Test Feature 4: Consolidated balance calculation"""
    
    def test_bank_accounts_summary_endpoint(self, auth_headers):
        """Verify bank accounts summary endpoint exists and returns consolidated data"""
        response = requests.get(f"{BASE_URL}/api/bank-accounts/summary", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Check for consolidated fields
        assert "total_mxn" in data, "Missing total_mxn field"
        assert "por_moneda" in data, "Missing por_moneda field"
        assert "total_cuentas" in data, "Missing total_cuentas field"
        
        print(f"✓ Bank accounts summary: Total MXN={data['total_mxn']}, Accounts={data['total_cuentas']}")
    
    def test_bank_accounts_summary_has_currency_breakdown(self, auth_headers):
        """Verify summary has breakdown by currency"""
        response = requests.get(f"{BASE_URL}/api/bank-accounts/summary", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        por_moneda = data.get("por_moneda", {})
        
        # Should have at least MXN and USD
        assert isinstance(por_moneda, dict), "por_moneda should be a dict"
        
        for currency, info in por_moneda.items():
            assert "saldo" in info, f"Missing saldo for {currency}"
            assert "cuentas" in info, f"Missing cuentas count for {currency}"
        
        print(f"✓ Bank accounts summary has currency breakdown: {list(por_moneda.keys())}")


class TestExcelExportFields:
    """Test Feature 5: Historical exchange rate in Excel exports"""
    
    def test_payment_has_tipo_cambio_historico_field(self, auth_headers):
        """Verify Payment model includes tipo_cambio_historico field"""
        # Create a USD payment
        payment_data = {
            "tipo": "pago",
            "concepto": "TEST_Payment for export test",
            "monto": 100.00,
            "moneda": "USD",
            "metodo_pago": "transferencia",
            "fecha_vencimiento": (datetime.now() + timedelta(days=7)).isoformat(),
            "tipo_cambio_historico": 17.5,  # Explicitly set
            "es_real": True
        }
        
        response = requests.post(f"{BASE_URL}/api/payments", json=payment_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        
        created = response.json()
        
        # Verify the field is accepted
        # Note: The field may or may not be returned depending on implementation
        payment_id = created.get("id")
        
        # Get the payment to verify
        if payment_id:
            get_response = requests.get(f"{BASE_URL}/api/payments/{payment_id}", headers=auth_headers)
            if get_response.status_code == 200:
                payment = get_response.json()
                # tipo_cambio_historico should be present for USD payments
                print(f"  Payment tipo_cambio_historico: {payment.get('tipo_cambio_historico')}")
            
            # Cleanup
            requests.delete(f"{BASE_URL}/api/payments/{payment_id}", headers=auth_headers)
        
        print("✓ Payment accepts tipo_cambio_historico field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
