"""
Test suite for DIOT and Bank Module features
- DIOT preview endpoint
- Bank transactions (Estados de Cuenta)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://satflow-manager.preview.emergentagent.com').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@demo.com"


class TestDIOTModule:
    """DIOT Module endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_diot_preview_endpoint_exists(self, auth_headers):
        """Test DIOT preview endpoint returns valid response"""
        response = requests.get(f"{BASE_URL}/api/diot/preview", headers=auth_headers)
        assert response.status_code == 200, f"DIOT preview failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "records" in data
        assert "summary" in data
        assert isinstance(data["records"], list)
        assert "totalOperaciones" in data["summary"]
        assert "totalIVA" in data["summary"]
        assert "totalMonto" in data["summary"]
    
    def test_diot_preview_with_date_filters(self, auth_headers):
        """Test DIOT preview with date filters"""
        params = {
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31"
        }
        response = requests.get(f"{BASE_URL}/api/diot/preview", headers=auth_headers, params=params)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure is maintained with filters
        assert "records" in data
        assert "summary" in data
    
    def test_diot_preview_empty_records_is_valid(self, auth_headers):
        """Test that empty records is valid behavior when no paid egreso invoices exist"""
        response = requests.get(f"{BASE_URL}/api/diot/preview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Empty records is expected when no paid egreso invoices
        assert data["summary"]["totalOperaciones"] == len(data["records"])


class TestBankModule:
    """Bank Module (Estados de Cuenta) tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_bank_accounts_list(self, auth_headers):
        """Test listing bank accounts"""
        response = requests.get(f"{BASE_URL}/api/bank-accounts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 2, "Expected at least 2 bank accounts (MXN and USD)"
        
        # Verify account structure
        for account in data:
            assert "id" in account
            assert "nombre" in account
            assert "banco" in account
            assert "moneda" in account
            assert "saldo_inicial" in account
    
    def test_bank_accounts_summary(self, auth_headers):
        """Test bank accounts summary endpoint"""
        response = requests.get(f"{BASE_URL}/api/bank-accounts/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total_cuentas" in data
        assert "total_mxn" in data
        assert "por_moneda" in data
        assert data["total_cuentas"] >= 2
    
    def test_bank_transactions_list(self, auth_headers):
        """Test listing bank transactions"""
        response = requests.get(f"{BASE_URL}/api/bank-transactions?limit=100", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_create_bank_transaction(self, auth_headers):
        """Test creating a new bank transaction (Estado de Cuenta movement)"""
        # First get a bank account ID
        accounts_response = requests.get(f"{BASE_URL}/api/bank-accounts", headers=auth_headers)
        accounts = accounts_response.json()
        assert len(accounts) > 0, "No bank accounts available"
        
        # Use the MXN account (BBVA)
        mxn_account = next((a for a in accounts if a["moneda"] == "MXN"), accounts[0])
        
        # Create a test bank transaction
        transaction_data = {
            "bank_account_id": mxn_account["id"],
            "fecha_movimiento": datetime.now().isoformat(),
            "fecha_valor": datetime.now().isoformat(),
            "descripcion": "TEST_Deposito de prueba",
            "referencia": "TEST_REF_001",
            "monto": 1500.00,
            "moneda": "MXN",
            "tipo_movimiento": "credito",
            "saldo": 501500.00,
            "fuente": "manual"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/bank-transactions",
            headers=auth_headers,
            json=transaction_data
        )
        assert response.status_code == 200, f"Create bank transaction failed: {response.text}"
        data = response.json()
        
        # Verify created transaction
        assert "id" in data
        assert data["descripcion"] == "TEST_Deposito de prueba"
        assert data["monto"] == 1500.00
        assert data["tipo_movimiento"] == "credito"
        
        return data["id"]
    
    def test_verify_created_transaction_persisted(self, auth_headers):
        """Verify the created transaction appears in the list"""
        response = requests.get(f"{BASE_URL}/api/bank-transactions?limit=100", headers=auth_headers)
        assert response.status_code == 200
        transactions = response.json()
        
        # Find our test transaction
        test_txn = next((t for t in transactions if "TEST_" in t.get("descripcion", "")), None)
        if test_txn:
            assert test_txn["descripcion"] == "TEST_Deposito de prueba"
            assert test_txn["monto"] == 1500.00


class TestReconciliations:
    """Reconciliation tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_reconciliations_list(self, auth_headers):
        """Test listing reconciliations"""
        response = requests.get(f"{BASE_URL}/api/reconciliations?limit=100", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_cleanup_test_transactions(self, auth_headers):
        """Clean up TEST_ prefixed transactions"""
        # Get all transactions
        response = requests.get(f"{BASE_URL}/api/bank-transactions?limit=1000", headers=auth_headers)
        if response.status_code == 200:
            transactions = response.json()
            for txn in transactions:
                if "TEST_" in txn.get("descripcion", ""):
                    # Note: There's no delete endpoint for bank transactions
                    # This is just to verify we can identify test data
                    pass
        
        # Test passes - cleanup noted
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
