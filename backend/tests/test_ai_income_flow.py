"""
Test AI Financial Analysis - Income Flow Analysis and Trends
Tests the /api/financial-statements/ai-analysis endpoint for:
1. income_flow_analysis presence and content
2. trends_analysis presence and content
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAIIncomeFlowAnalysis:
    """Tests for AI income_flow_analysis feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_ai_analysis_endpoint_returns_200(self):
        """Test that AI analysis endpoint returns 200 for valid period"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_ai_analysis_contains_income_flow_analysis(self):
        """Test that response contains income_flow_analysis field"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check analysis object exists
        assert "analysis" in data, "Response missing 'analysis' field"
        analysis = data["analysis"]
        
        # Check income_flow_analysis exists
        assert "income_flow_analysis" in analysis, "Analysis missing 'income_flow_analysis' field"
    
    def test_income_flow_analysis_has_content(self):
        """Test that income_flow_analysis contains actual analysis text (not empty)"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        income_flow = data["analysis"].get("income_flow_analysis", "")
        
        # Should not be empty or null
        assert income_flow is not None, "income_flow_analysis is None"
        assert len(income_flow) > 50, f"income_flow_analysis too short ({len(income_flow)} chars), expected substantial analysis"
        
        # Should contain financial terms (Spanish)
        financial_terms = ["costo", "ventas", "margen", "utilidad", "ingresos", "gastos"]
        has_financial_term = any(term in income_flow.lower() for term in financial_terms)
        assert has_financial_term, f"income_flow_analysis doesn't contain expected financial terms: {income_flow[:200]}"
    
    def test_ai_analysis_contains_trends_analysis(self):
        """Test that response contains trends_analysis field when multiple periods exist"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        analysis = data["analysis"]
        
        # trends_analysis should be present when there are multiple periods
        assert "trends_analysis" in analysis, "Analysis missing 'trends_analysis' field"
    
    def test_trends_analysis_has_content(self):
        """Test that trends_analysis contains actual analysis text"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        trends = data["analysis"].get("trends_analysis", "")
        
        # Should not be empty
        assert trends is not None, "trends_analysis is None"
        assert len(trends) > 50, f"trends_analysis too short ({len(trends)} chars)"
    
    def test_ai_analysis_response_structure(self):
        """Test complete response structure"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level fields
        assert "period_type" in data
        assert "period_value" in data
        assert "periods_included" in data
        assert "company_name" in data
        assert "analysis" in data
        
        # Check analysis fields
        analysis = data["analysis"]
        required_fields = [
            "executive_summary",
            "profitability_analysis",
            "returns_analysis",
            "liquidity_analysis",
            "solvency_analysis",
            "income_flow_analysis",
            "recommendations"
        ]
        
        for field in required_fields:
            assert field in analysis, f"Analysis missing required field: {field}"
            assert analysis[field] is not None, f"Field {field} is None"
            assert len(analysis[field]) > 20, f"Field {field} has insufficient content"
    
    def test_ai_analysis_generated_by_ai(self):
        """Test that analysis is generated by AI (not default)"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-03", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        analysis = data["analysis"]
        
        # Check generated_by field
        assert analysis.get("generated_by") == "AI", f"Expected generated_by='AI', got '{analysis.get('generated_by')}'"
        assert analysis.get("model") == "gpt-5.2", f"Expected model='gpt-5.2', got '{analysis.get('model')}'"
    
    def test_ai_analysis_different_period(self):
        """Test AI analysis for a different period (2024-02)"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2024-02", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "income_flow_analysis" in data["analysis"]
        assert len(data["analysis"]["income_flow_analysis"]) > 50
    
    def test_ai_analysis_nonexistent_period_returns_404(self):
        """Test that nonexistent period returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            params={"period_type": "monthly", "period_value": "2099-12", "language": "es"},
            headers=self.headers
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
