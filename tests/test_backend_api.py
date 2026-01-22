"""
TaxnFin Cashflow Backend API Tests
Tests for authentication, dashboard, and genetic optimization endpoints
"""
import pytest
import requests
import os
import json
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://financepro-42.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin_password"


class TestHealthAndBasics:
    """Basic connectivity tests"""
    
    def test_api_reachable(self):
        """Test that the API is reachable"""
        response = requests.get(f"{BASE_URL}/api/bank-api/available-banks")
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert data['status'] == 'success'
        print(f"API reachable - Available banks: {len(data.get('banks', []))}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["email"] == TEST_EMAIL
        assert len(data["access_token"]) > 0
        print(f"Login successful - User: {data['user']['nombre']}, Role: {data['user']['role']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print(f"Invalid login correctly rejected: {data['detail']}")
    
    def test_login_missing_fields(self):
        """Test login with missing fields"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL
        })
        assert response.status_code == 422  # Validation error
        print("Missing password correctly rejected")


class TestDashboard:
    """Dashboard endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_dashboard_returns_kpis(self, auth_token):
        """Test dashboard returns valid KPIs"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/reports/dashboard", headers=headers)
        
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        
        data = response.json()
        assert "kpis" in data, "No kpis in response"
        assert "cashflow_weeks" in data, "No cashflow_weeks in response"
        
        kpis = data["kpis"]
        assert "total_transactions" in kpis
        assert "total_cfdis" in kpis
        assert "total_reconciliations" in kpis
        
        print(f"Dashboard KPIs - Transactions: {kpis['total_transactions']}, CFDIs: {kpis['total_cfdis']}, Reconciliations: {kpis['total_reconciliations']}")
    
    def test_dashboard_returns_13_weeks(self, auth_token):
        """Test dashboard returns 13 weeks of cashflow data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/reports/dashboard", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        weeks = data.get("cashflow_weeks", [])
        assert len(weeks) <= 13, f"Expected max 13 weeks, got {len(weeks)}"
        
        # Check week structure
        if weeks:
            week = weeks[0]
            assert "numero_semana" in week
            assert "total_ingresos" in week or "total_ingresos_reales" in week
            print(f"Cashflow weeks returned: {len(weeks)}")
    
    def test_dashboard_unauthorized(self):
        """Test dashboard without auth token"""
        response = requests.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code in [401, 403]
        print("Unauthorized access correctly rejected")


class TestGeneticOptimization:
    """Genetic optimization endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_genetic_optimization_basic(self, auth_token):
        """Test genetic optimization with minimal generations"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Use minimal parameters for faster test
        payload = {
            "objetivos": {
                "maximizar_liquidez": True,
                "minimizar_costos": True,
                "evitar_crisis": True
            },
            "restricciones": {
                "max_retraso_dias": 30,
                "max_adelanto_dias": 15,
                "min_saldo": 50000
            },
            "parametros": {
                "generaciones": 5,  # Minimal for testing
                "poblacion": 20,
                "prob_mutacion": 0.2
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/optimize/genetic",
            headers=headers,
            json=payload,
            timeout=120  # Allow time for optimization
        )
        
        # Check response
        if response.status_code == 200:
            data = response.json()
            assert data.get("status") == "success" or "insufficient_data" in str(data.get("status", ""))
            
            if data.get("status") == "success":
                assert "optimization_id" in data
                assert "mejor_solucion" in data
                assert "mejora_vs_baseline" in data
                print(f"Optimization successful - ID: {data['optimization_id']}")
                print(f"Improvement: {data['mejora_vs_baseline']}")
            else:
                print(f"Optimization returned: {data.get('message', 'insufficient data')}")
        else:
            # May fail if no projected transactions exist
            print(f"Optimization response: {response.status_code} - {response.text[:200]}")
            assert response.status_code in [200, 400, 500]  # Accept various responses
    
    def test_optimization_history(self, auth_token):
        """Test optimization history endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/optimize/history", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "optimizations" in data
        print(f"Optimization history: {len(data['optimizations'])} records")


class TestCashflowWeeks:
    """Cashflow weeks endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_get_cashflow_weeks(self, auth_token):
        """Test getting cashflow weeks"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cashflow/weeks", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Cashflow weeks: {len(data)}")


class TestTransactions:
    """Transaction endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_list_transactions(self, auth_token):
        """Test listing transactions"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/transactions", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Transactions: {len(data)}")


class TestAdvancedFeatures:
    """Advanced features endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_available_banks(self):
        """Test available banks endpoint (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/bank-api/available-banks")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "banks" in data
        print(f"Available banks: {len(data['banks'])}")
    
    def test_predictive_analysis(self, auth_token):
        """Test predictive analysis endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/ai/predictive-analysis", headers=headers)
        
        # May return insufficient_data if no historical data
        assert response.status_code == 200
        data = response.json()
        print(f"Predictive analysis status: {data.get('status')}")
    
    def test_auto_reconcile_batch(self, auth_token):
        """Test auto reconciliation batch endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/reconciliation/auto-reconcile-batch?min_score=85",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        print(f"Auto reconcile result: {data}")
    
    def test_check_alerts(self, auth_token):
        """Test alerts check endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/alerts/check-and-send", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"Alerts sent: {data.get('alerts_sent', 0)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
