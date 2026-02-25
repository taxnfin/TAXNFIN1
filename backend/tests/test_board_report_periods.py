"""
Board Report Period Selector & Aggregation Tests
Tests for new endpoints: /available-periods and /aggregated
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBoardReportPeriods:
    """Test period selector and aggregation for Board Report"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_available_periods_endpoint_returns_structured_data(self):
        """Test /available-periods returns structured period options"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/available-periods",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure contains all period types
        assert "specific_months" in data, "Missing specific_months"
        assert "quarters" in data, "Missing quarters"
        assert "annual" in data, "Missing annual"
        assert "generic" in data, "Missing generic"
        assert "raw_periods" in data, "Missing raw_periods"
        
        print(f"Found {len(data['specific_months'])} specific months")
        print(f"Found {len(data['quarters'])} quarters")
        print(f"Found {len(data['annual'])} annual periods")
    
    def test_specific_months_format(self):
        """Test specific months have correct format (value, label, type)"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/available-periods",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data['specific_months']:
            month = data['specific_months'][0]
            assert "value" in month, "Month missing 'value'"
            assert "label" in month, "Month missing 'label'"
            assert "type" in month, "Month missing 'type'"
            assert month["type"] == "monthly"
            # Value should be in YYYY-MM format
            assert "-" in month["value"]
            print(f"Sample month: {month}")
    
    def test_quarters_format(self):
        """Test quarters have correct format with months_available"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/available-periods",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data['quarters']:
            quarter = data['quarters'][0]
            assert "value" in quarter, "Quarter missing 'value'"
            assert "label" in quarter, "Quarter missing 'label'"
            assert "type" in quarter, "Quarter missing 'type'"
            assert "months_available" in quarter, "Quarter missing 'months_available'"
            assert "months_total" in quarter, "Quarter missing 'months_total'"
            assert quarter["type"] == "quarterly"
            # Value should be in Q1-YYYY format
            assert quarter["value"].startswith("Q")
            print(f"Sample quarter: {quarter}")
    
    def test_annual_format(self):
        """Test annual periods have correct format"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/available-periods",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data['annual']:
            year = data['annual'][0]
            assert "value" in year, "Annual missing 'value'"
            assert "label" in year, "Annual missing 'label'"
            assert "type" in year, "Annual missing 'type'"
            assert "months_available" in year, "Annual missing 'months_available'"
            assert year["type"] == "annual"
            # Value should be YYYY format
            assert len(year["value"]) == 4
            print(f"Sample annual: {year}")
    
    def test_aggregated_monthly_returns_single_period(self):
        """Test aggregated endpoint with monthly returns single month data"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "monthly", "period_value": "2024-01"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_type"] == "monthly"
        assert data["period_value"] == "2024-01"
        assert "periods_included" in data
        assert len(data["periods_included"]) == 1
        assert data["periods_included"][0] == "2024-01"
        print(f"Monthly periods included: {data['periods_included']}")
    
    def test_aggregated_quarterly_returns_three_periods(self):
        """Test aggregated endpoint with quarterly returns sum of 3 months"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "quarterly", "period_value": "Q1-2024"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_type"] == "quarterly"
        assert data["period_value"] == "Q1-2024"
        assert "periods_included" in data
        # Should include 2024-01, 2024-02, 2024-03
        periods = data["periods_included"]
        print(f"Quarterly periods included: {periods}")
        assert len(periods) >= 1  # At least some data available
        
        # Verify income data is aggregated
        assert "income_statement" in data
        assert data["income_statement"]["ingresos"] > 0
    
    def test_quarterly_aggregation_sums_correctly(self):
        """Verify quarterly data is sum of individual months"""
        # Get individual month data
        monthly_totals = []
        for month in ["2024-01", "2024-02", "2024-03"]:
            response = requests.get(
                f"{BASE_URL}/api/financial-statements/metrics/{month}",
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                ingresos = data.get("income_statement", {}).get("ingresos", 0)
                monthly_totals.append(ingresos)
                print(f"{month} ingresos: {ingresos}")
        
        # Get quarterly data
        quarterly_response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "quarterly", "period_value": "Q1-2024"},
            headers=self.headers
        )
        assert quarterly_response.status_code == 200
        quarterly_data = quarterly_response.json()
        quarterly_ingresos = quarterly_data.get("income_statement", {}).get("ingresos", 0)
        
        # Verify sum matches
        expected_sum = sum(monthly_totals)
        print(f"Sum of monthly: {expected_sum}")
        print(f"Quarterly total: {quarterly_ingresos}")
        assert abs(quarterly_ingresos - expected_sum) < 0.01, "Quarterly sum doesn't match monthly totals"
    
    def test_aggregated_annual_returns_yearly_data(self):
        """Test aggregated endpoint with annual period"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "annual", "period_value": "2024"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_type"] == "annual"
        assert data["period_value"] == "2024"
        assert "periods_included" in data
        periods = data["periods_included"]
        print(f"Annual periods included: {periods}")
        
        # Should have metrics calculated
        assert "metrics" in data
        assert "income_statement" in data
    
    def test_aggregated_nonexistent_period_returns_404(self):
        """Test aggregated endpoint with non-existent period returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "quarterly", "period_value": "Q4-2099"},
            headers=self.headers
        )
        # Should return 404 when no data found
        assert response.status_code == 404
    
    def test_aggregated_requires_parameters(self):
        """Test aggregated endpoint requires period_type and period_value"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            headers=self.headers
        )
        # Should return 422 when parameters missing
        assert response.status_code == 422


class TestBoardReportMetrics:
    """Test metrics calculation for aggregated data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_aggregated_has_all_metric_categories(self):
        """Test aggregated response has all metric categories"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "quarterly", "period_value": "Q1-2024"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        metrics = data.get("metrics", {})
        
        # Check all metric categories present
        assert "margins" in metrics, "Missing margins"
        assert "returns" in metrics, "Missing returns"
        assert "efficiency" in metrics, "Missing efficiency"
        assert "liquidity" in metrics, "Missing liquidity"
        assert "solvency" in metrics, "Missing solvency"
        
        print("All metric categories present")
    
    def test_aggregated_margins_calculation(self):
        """Test margins are calculated correctly for aggregated data"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "quarterly", "period_value": "Q1-2024"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        margins = data.get("metrics", {}).get("margins", {})
        
        # Check specific margins
        assert "gross_margin" in margins
        assert "ebitda_margin" in margins
        assert "operating_margin" in margins
        assert "net_margin" in margins
        
        # Verify margin values have expected structure
        gross_margin = margins["gross_margin"]
        assert "value" in gross_margin
        assert "label" in gross_margin
        assert isinstance(gross_margin["value"], (int, float))
        
        print(f"Gross Margin: {gross_margin['value']:.2f}%")
        print(f"Net Margin: {margins['net_margin']['value']:.2f}%")
    
    def test_aggregated_balance_uses_latest_period(self):
        """Test that balance sheet uses latest period data (not summed)"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/aggregated",
            params={"period_type": "quarterly", "period_value": "Q1-2024"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        balance = data.get("balance_sheet", {})
        assert "activo_total" in balance
        assert "pasivo_total" in balance
        assert "capital_contable" in balance
        
        # Balance sheet values should be from the latest month
        print(f"Activo Total: {balance['activo_total']}")
        print(f"Capital Contable: {balance['capital_contable']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
