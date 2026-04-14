"""
Test KPI Metrics and Optimization Apply Endpoint
Tests for:
1. Financial metrics API returns components for all metrics
2. Optimization apply endpoint error handling
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFinancialMetricsComponents:
    """Test that financial metrics API returns components for breakdown display"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_periods(self):
        """Test GET /api/financial-statements/periods returns available periods"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=self.headers
        )
        assert response.status_code == 200
        periods = response.json()
        assert isinstance(periods, list)
        assert len(periods) > 0
        # Verify period structure
        period = periods[0]
        assert 'periodo' in period
        assert 'has_income_statement' in period
        assert 'has_balance_sheet' in period
    
    def test_metrics_margins_have_components(self):
        """Test that margin metrics include components array"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        margins = data.get('metrics', {}).get('margins', {})
        
        # Test gross_margin
        gross_margin = margins.get('gross_margin', {})
        assert 'components' in gross_margin, "gross_margin missing components"
        assert len(gross_margin['components']) >= 2, "gross_margin should have at least 2 components"
        assert 'formula' in gross_margin, "gross_margin missing formula"
        assert 'label' in gross_margin, "gross_margin missing label"
        
        # Verify component structure
        for comp in gross_margin['components']:
            assert 'label' in comp, "Component missing label"
            assert 'value' in comp, "Component missing value"
        
        # Test other margins
        for margin_key in ['ebitda_margin', 'operating_margin', 'net_margin', 'nopat_margin']:
            margin = margins.get(margin_key, {})
            assert 'components' in margin, f"{margin_key} missing components"
    
    def test_metrics_returns_have_components(self):
        """Test that return metrics include components array"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        returns = data.get('metrics', {}).get('returns', {})
        
        for return_key in ['roic', 'roe', 'roce', 'roa']:
            metric = returns.get(return_key, {})
            assert 'components' in metric, f"{return_key} missing components"
            assert 'formula' in metric, f"{return_key} missing formula"
    
    def test_metrics_liquidity_have_components(self):
        """Test that liquidity metrics include components array"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        liquidity = data.get('metrics', {}).get('liquidity', {})
        
        # Test working_capital specifically
        working_capital = liquidity.get('working_capital', {})
        assert 'components' in working_capital, "working_capital missing components"
        assert 'formula' in working_capital, "working_capital missing formula"
        
        # Verify working_capital components have correct labels
        comp_labels = [c['label'] for c in working_capital['components']]
        assert 'Activo Circulante' in comp_labels, "Missing Activo Circulante component"
        assert 'Pasivo Circulante' in comp_labels, "Missing Pasivo Circulante component"
        
        # Test other liquidity metrics
        for liq_key in ['current_ratio', 'quick_ratio', 'cash_ratio']:
            metric = liquidity.get(liq_key, {})
            assert 'components' in metric, f"{liq_key} missing components"
    
    def test_metrics_solvency_have_components(self):
        """Test that solvency metrics include components array"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        solvency = data.get('metrics', {}).get('solvency', {})
        
        for solv_key in ['debt_to_equity', 'debt_to_assets', 'interest_coverage', 'equity_ratio']:
            metric = solvency.get(solv_key, {})
            assert 'components' in metric, f"{solv_key} missing components"
            assert 'formula' in metric, f"{solv_key} missing formula"
    
    def test_metrics_efficiency_have_components(self):
        """Test that efficiency metrics include components array"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        efficiency = data.get('metrics', {}).get('efficiency', {})
        
        for eff_key in ['asset_turnover', 'dso', 'dpo', 'cash_conversion_cycle']:
            metric = efficiency.get(eff_key, {})
            assert 'components' in metric, f"{eff_key} missing components"


class TestOptimizationApplyErrorHandling:
    """Test optimization apply endpoint error handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_apply_nonexistent_optimization_returns_404(self):
        """Test POST /api/optimize/apply/{id} returns 404 for non-existent optimization"""
        response = requests.post(
            f"{BASE_URL}/api/optimize/apply/nonexistent-id",
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert 'detail' in data, "Response should contain detail field"
        assert 'no encontrada' in data['detail'].lower() or 'not found' in data['detail'].lower()
    
    def test_apply_optimization_without_auth_returns_401(self):
        """Test POST /api/optimize/apply/{id} returns 401 without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/optimize/apply/some-id"
        )
        # Should return 401 or 403 for unauthenticated request
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
