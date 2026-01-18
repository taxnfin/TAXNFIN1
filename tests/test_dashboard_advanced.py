"""
Test Dashboard Advanced Features - TaxnFin Cashflow
Tests for: Currency selector, Bank account filter, KPIs, Charts, Cash Pooling, Risk Indicators
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"


class TestDashboardAdvanced:
    """Dashboard Advanced Features Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token")
            self.user = data.get("user")
            self.company_id = self.user.get("company_id")
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "X-Company-ID": self.company_id
            })
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    # ===== AUTHENTICATION TESTS =====
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
    
    # ===== DASHBOARD ENDPOINT TESTS =====
    
    def test_dashboard_loads_default_mxn(self):
        """Test dashboard loads with default MXN currency"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "moneda_vista" in data
        assert data["moneda_vista"] == "MXN"
        assert "cashflow_weeks" in data
        assert "saldo_inicial_bancos" in data
        assert "saldo_final_proyectado" in data
        assert "kpis" in data
        print(f"Dashboard loaded with MXN - Saldo Inicial: {data['saldo_inicial_bancos']}")
    
    def test_dashboard_currency_selector_mxn(self):
        """Test dashboard with MXN currency parameter"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard?moneda_vista=MXN")
        assert response.status_code == 200
        data = response.json()
        assert data["moneda_vista"] == "MXN"
        print(f"MXN - Saldo Inicial: {data['saldo_inicial_bancos']}, Saldo Final: {data['saldo_final_proyectado']}")
    
    def test_dashboard_currency_selector_usd(self):
        """Test dashboard with USD currency parameter - values should be converted"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard?moneda_vista=USD")
        assert response.status_code == 200
        data = response.json()
        assert data["moneda_vista"] == "USD"
        
        # Verify FX rates are used
        assert "fx_rates_used" in data
        assert "USD" in data["fx_rates_used"]
        print(f"USD - Saldo Inicial: {data['saldo_inicial_bancos']}, FX Rate: {data['fx_rates_used']['USD']}")
    
    def test_dashboard_currency_selector_eur(self):
        """Test dashboard with EUR currency parameter - values should be converted"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard?moneda_vista=EUR")
        assert response.status_code == 200
        data = response.json()
        assert data["moneda_vista"] == "EUR"
        
        # Verify FX rates are used
        assert "fx_rates_used" in data
        assert "EUR" in data["fx_rates_used"]
        print(f"EUR - Saldo Inicial: {data['saldo_inicial_bancos']}, FX Rate: {data['fx_rates_used']['EUR']}")
    
    def test_dashboard_currency_conversion_values_differ(self):
        """Test that currency conversion produces different values"""
        response_mxn = self.session.get(f"{BASE_URL}/api/reports/dashboard?moneda_vista=MXN")
        response_usd = self.session.get(f"{BASE_URL}/api/reports/dashboard?moneda_vista=USD")
        
        assert response_mxn.status_code == 200
        assert response_usd.status_code == 200
        
        data_mxn = response_mxn.json()
        data_usd = response_usd.json()
        
        # MXN values should be higher than USD (since USD rate is ~17.50)
        if data_mxn["saldo_inicial_bancos"] > 0:
            assert data_mxn["saldo_inicial_bancos"] > data_usd["saldo_inicial_bancos"], \
                "MXN values should be higher than USD converted values"
        print(f"MXN: {data_mxn['saldo_inicial_bancos']}, USD: {data_usd['saldo_inicial_bancos']}")
    
    # ===== BANK ACCOUNT FILTER TESTS =====
    
    def test_get_bank_accounts_list(self):
        """Test getting list of bank accounts for filter dropdown"""
        response = self.session.get(f"{BASE_URL}/api/bank-accounts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} bank accounts")
        
        if len(data) > 0:
            # Verify account structure
            account = data[0]
            assert "id" in account
            assert "nombre" in account or "nombre_banco" in account
    
    def test_dashboard_with_bank_account_filter(self):
        """Test dashboard filtered by specific bank account"""
        # First get bank accounts
        accounts_response = self.session.get(f"{BASE_URL}/api/bank-accounts")
        if accounts_response.status_code != 200:
            pytest.skip("Could not get bank accounts")
        
        accounts = accounts_response.json()
        if len(accounts) == 0:
            pytest.skip("No bank accounts available for filtering")
        
        account_id = accounts[0]["id"]
        
        # Get dashboard filtered by account
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard?bank_account_id={account_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify data is returned
        assert "cashflow_weeks" in data
        assert "saldo_inicial_bancos" in data
        print(f"Dashboard filtered by account {account_id}: Saldo = {data['saldo_inicial_bancos']}")
    
    def test_dashboard_with_both_filters(self):
        """Test dashboard with both currency and bank account filters"""
        # Get bank accounts
        accounts_response = self.session.get(f"{BASE_URL}/api/bank-accounts")
        if accounts_response.status_code != 200 or len(accounts_response.json()) == 0:
            pytest.skip("No bank accounts available")
        
        account_id = accounts_response.json()[0]["id"]
        
        # Test with both filters
        response = self.session.get(
            f"{BASE_URL}/api/reports/dashboard?moneda_vista=USD&bank_account_id={account_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["moneda_vista"] == "USD"
        print(f"Dashboard with USD + account filter: Saldo = {data['saldo_inicial_bancos']}")
    
    # ===== KPI TESTS =====
    
    def test_dashboard_kpis_structure(self):
        """Test that KPIs are returned with correct structure"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "kpis" in data
        kpis = data["kpis"]
        
        # Verify all KPI fields
        assert "total_transactions" in kpis
        assert "total_cfdis" in kpis
        assert "total_reconciliations" in kpis
        assert "total_customers" in kpis
        assert "total_vendors" in kpis
        
        # Verify values are integers
        assert isinstance(kpis["total_transactions"], int)
        assert isinstance(kpis["total_cfdis"], int)
        assert isinstance(kpis["total_reconciliations"], int)
        assert isinstance(kpis["total_customers"], int)
        assert isinstance(kpis["total_vendors"], int)
        
        print(f"KPIs: Transactions={kpis['total_transactions']}, CFDIs={kpis['total_cfdis']}, "
              f"Reconciliations={kpis['total_reconciliations']}, Customers={kpis['total_customers']}, "
              f"Vendors={kpis['total_vendors']}")
    
    def test_dashboard_main_kpis(self):
        """Test main KPIs: Saldo Inicial, Saldo Final Proyectado, Flujo Promedio"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Saldo Inicial
        assert "saldo_inicial_bancos" in data
        assert isinstance(data["saldo_inicial_bancos"], (int, float))
        
        # Saldo Final Proyectado
        assert "saldo_final_proyectado" in data
        assert isinstance(data["saldo_final_proyectado"], (int, float))
        
        # Trend with average flow
        assert "trend" in data
        assert "avg_flow_4w" in data["trend"]
        assert "direction" in data["trend"]
        assert data["trend"]["direction"] in ["up", "down", "stable"]
        
        print(f"Saldo Inicial: {data['saldo_inicial_bancos']}, "
              f"Saldo Final: {data['saldo_final_proyectado']}, "
              f"Flujo Promedio 4w: {data['trend']['avg_flow_4w']}, "
              f"Tendencia: {data['trend']['direction']}")
    
    # ===== CASHFLOW CHART DATA TESTS =====
    
    def test_dashboard_13_week_cashflow_data(self):
        """Test that 13-week cashflow data is returned for chart"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "cashflow_weeks" in data
        weeks = data["cashflow_weeks"]
        
        # Should have up to 13 weeks
        assert len(weeks) <= 13
        
        if len(weeks) > 0:
            week = weeks[0]
            # Verify week structure for chart
            assert "numero_semana" in week or "fecha_inicio" in week
            assert "total_ingresos" in week
            assert "total_egresos" in week
            assert "flujo_neto" in week
            assert "saldo_inicial" in week
            assert "saldo_final" in week
            
            print(f"Week 1: Ingresos={week['total_ingresos']}, Egresos={week['total_egresos']}, "
                  f"Flujo Neto={week['flujo_neto']}")
    
    def test_dashboard_variance_data(self):
        """Test that variance data is returned for variance chart"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        weeks = data.get("cashflow_weeks", [])
        
        if len(weeks) > 1:
            # First week should have 0 variance, subsequent weeks should have variance
            assert "varianza_flujo" in weeks[0]
            assert "varianza_pct" in weeks[0]
            
            # Check second week has variance calculated
            assert "varianza_flujo" in weeks[1]
            print(f"Week 2 variance: {weeks[1]['varianza_flujo']} ({weeks[1].get('varianza_pct', 0)}%)")
    
    # ===== CASH POOLING TESTS =====
    
    def test_dashboard_cash_pooling_data(self):
        """Test cash pooling section shows currency breakdown"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "cash_pool" in data
        cash_pool = data["cash_pool"]
        
        # Cash pool should be a dict with currency keys
        assert isinstance(cash_pool, dict)
        
        for currency, pool_data in cash_pool.items():
            assert "total" in pool_data
            assert "cuentas" in pool_data
            assert isinstance(pool_data["total"], (int, float))
            assert isinstance(pool_data["cuentas"], int)
            print(f"Cash Pool {currency}: Total={pool_data['total']}, Cuentas={pool_data['cuentas']}")
    
    # ===== BANK ACCOUNTS DETAIL TESTS =====
    
    def test_dashboard_bank_accounts_detail(self):
        """Test account details section shows bank accounts"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "bank_accounts" in data
        accounts = data["bank_accounts"]
        
        if len(accounts) > 0:
            account = accounts[0]
            # Verify account detail structure
            assert "id" in account
            assert "saldo_inicial" in account or "saldo_mxn" in account
            assert "moneda" in account
            
            # Risk indicators
            assert "riesgo_ocioso" in account
            assert "riesgo_bajo_saldo" in account
            
            print(f"Account: {account.get('nombre', account.get('nombre_banco', 'N/A'))}, "
                  f"Saldo: {account.get('saldo_inicial', 0)}, "
                  f"Riesgo Ocioso: {account['riesgo_ocioso']}, "
                  f"Riesgo Bajo: {account['riesgo_bajo_saldo']}")
    
    # ===== RISK INDICATORS TESTS =====
    
    def test_dashboard_risk_indicators(self):
        """Test risk indicators are returned"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "risk_indicators" in data
        risks = data["risk_indicators"]
        
        # Verify risk indicator fields
        assert "liquidez_critica" in risks
        assert "tendencia_negativa" in risks
        assert "saldos_ociosos" in risks
        assert "cuentas_bajo_saldo" in risks
        assert "semanas_con_deficit" in risks
        
        # Verify types
        assert isinstance(risks["liquidez_critica"], bool)
        assert isinstance(risks["tendencia_negativa"], bool)
        assert isinstance(risks["saldos_ociosos"], int)
        assert isinstance(risks["cuentas_bajo_saldo"], int)
        assert isinstance(risks["semanas_con_deficit"], int)
        
        print(f"Risk Indicators: Liquidez Crítica={risks['liquidez_critica']}, "
              f"Tendencia Negativa={risks['tendencia_negativa']}, "
              f"Saldos Ociosos={risks['saldos_ociosos']}, "
              f"Cuentas Bajo Saldo={risks['cuentas_bajo_saldo']}, "
              f"Semanas con Déficit={risks['semanas_con_deficit']}")
    
    # ===== FX RATES TESTS =====
    
    def test_dashboard_fx_rates_returned(self):
        """Test that FX rates used are returned"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "fx_rates_used" in data
        fx_rates = data["fx_rates_used"]
        
        # Should have at least MXN, USD, EUR
        assert "MXN" in fx_rates
        assert fx_rates["MXN"] == 1.0  # MXN is base
        
        # USD and EUR should have default rates if not configured
        if "USD" in fx_rates:
            assert fx_rates["USD"] > 0
        if "EUR" in fx_rates:
            assert fx_rates["EUR"] > 0
        
        print(f"FX Rates: {fx_rates}")
    
    # ===== UNAUTHORIZED ACCESS TEST =====
    
    def test_dashboard_unauthorized(self):
        """Test dashboard returns 401 without authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code in [401, 403]
        print("Unauthorized access correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
