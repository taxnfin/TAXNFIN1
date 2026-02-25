"""
Test AI Analysis Endpoint and PDF Export functionality
Tests for iteration 13 - AI Financial Analysis feature
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://finance-exec-report.preview.emergentagent.com')

class TestAIAnalysisEndpoint:
    """Tests for /api/financial-statements/ai-analysis endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_ai_analysis_monthly_returns_200(self):
        """Test AI analysis for monthly period returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "monthly",
                "period_value": "2024-01",
                "language": "es"
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_ai_analysis_returns_correct_structure(self):
        """Test AI analysis response has all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "monthly",
                "period_value": "2024-03",
                "language": "es"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level fields
        assert "period_type" in data, "Missing period_type"
        assert "period_value" in data, "Missing period_value"
        assert "periods_included" in data, "Missing periods_included"
        assert "company_name" in data, "Missing company_name"
        assert "analysis" in data, "Missing analysis"
    
    def test_ai_analysis_has_all_sections(self):
        """Test AI analysis has all required analysis sections"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "monthly",
                "period_value": "2024-02",
                "language": "es"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        analysis = data.get("analysis", {})
        
        # Check all analysis sections
        required_sections = [
            "executive_summary",
            "profitability_analysis",
            "returns_analysis",
            "liquidity_analysis",
            "solvency_analysis",
            "recommendations",
            "generated_by"
        ]
        
        for section in required_sections:
            assert section in analysis, f"Missing analysis section: {section}"
            # Verify section has content (non-empty string)
            assert analysis[section], f"Empty content for section: {section}"
    
    def test_ai_analysis_quarterly_aggregation(self):
        """Test AI analysis works with quarterly period"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "quarterly",
                "period_value": "Q1-2024",
                "language": "es"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Quarterly should include multiple periods
        periods = data.get("periods_included", [])
        assert len(periods) > 0, "Should have at least one period"
    
    def test_ai_analysis_english_language(self):
        """Test AI analysis works with English language"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "monthly",
                "period_value": "2024-01",
                "language": "en"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        analysis = data.get("analysis", {})
        
        # Should have content
        assert analysis.get("executive_summary"), "Missing executive summary"
    
    def test_ai_analysis_invalid_period_returns_404(self):
        """Test AI analysis returns 404 for non-existent period"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "monthly",
                "period_value": "2020-01",  # Non-existent period
                "language": "es"
            },
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404 for non-existent period, got {response.status_code}"
    
    def test_ai_analysis_generated_by_ai_or_default(self):
        """Test analysis is generated by AI or has default fallback"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={
                "period_type": "monthly",
                "period_value": "2024-03",
                "language": "es"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        analysis = data.get("analysis", {})
        
        generated_by = analysis.get("generated_by")
        assert generated_by in ["AI", "Default"], f"generated_by should be 'AI' or 'Default', got: {generated_by}"


class TestFinancialStatementEndpoints:
    """Additional tests for financial statement endpoints used by Board Report"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_available_periods_returns_data(self):
        """Test available periods endpoint returns structured data"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/available-periods",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "specific_months" in data
        assert "quarters" in data
        assert "annual" in data
        assert len(data["specific_months"]) > 0, "Should have at least one month"
    
    def test_metrics_endpoint_returns_data(self):
        """Test metrics endpoint returns financial data"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "metrics" in data
        assert "income_statement" in data
        assert "balance_sheet" in data
    
    def test_sankey_endpoint_returns_data(self):
        """Test Sankey diagram endpoint returns flow data"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/sankey/2024-03",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "nodes" in data
        assert "links" in data
        assert "summary" in data
    
    def test_trends_endpoint_returns_historical_data(self):
        """Test trends endpoint returns historical periods"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/trends",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "periods_count" in data
        assert data["periods_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
