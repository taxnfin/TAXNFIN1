"""
Test AI Analysis and Genetic Optimization Features
Tests for the TaxnFin bug fixes:
1. Genetic Optimization should show descriptive error when insufficient data
2. AI Analysis endpoint should return income_flow_analysis and trends_analysis
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://finance-exec-report.preview.emergentagent.com').rstrip('/')


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@demo.com"


class TestGeneticOptimization:
    """Tests for genetic optimization with descriptive error messages"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_genetic_optimization_insufficient_data(self):
        """
        Test that genetic optimization returns a descriptive error message
        when there are insufficient projected transactions (< 5)
        """
        response = requests.post(
            f"{BASE_URL}/api/optimize/genetic",
            headers=self.headers,
            json={
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
                    "generaciones": 50,
                    "poblacion": 100,
                    "prob_mutacion": 0.2
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return insufficient_data status with descriptive message
        assert data.get("status") == "insufficient_data", f"Expected 'insufficient_data' status, got: {data}"
        assert "message" in data
        # Check that message mentions the 5 transaction requirement
        assert "5" in data["message"] or "transacciones" in data["message"].lower(), \
            f"Message should mention 5 transactions requirement: {data['message']}"
        
        print(f"✓ Genetic optimization error message: {data['message']}")


class TestAIAnalysis:
    """Tests for AI Analysis endpoint with income_flow_analysis and trends_analysis"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_available_periods(self):
        """Test that we have financial data available for testing"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=self.headers
        )
        assert response.status_code == 200
        periods = response.json()
        assert len(periods) > 0, "No financial periods found for testing"
        print(f"✓ Found {len(periods)} periods: {[p['periodo'] for p in periods]}")
        return periods
    
    def test_ai_analysis_returns_all_sections(self):
        """
        Test that AI analysis endpoint returns all required sections including:
        - executive_summary
        - profitability_analysis
        - returns_analysis
        - liquidity_analysis
        - solvency_analysis
        - recommendations
        - income_flow_analysis (NEW - for Flujo del Estado de Resultados)
        - trends_analysis (NEW - for historical trends)
        """
        # Get available periods first
        periods_response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=self.headers
        )
        assert periods_response.status_code == 200
        periods = periods_response.json()
        assert len(periods) > 0, "No periods available"
        
        period = periods[0]["periodo"]  # Use first available period
        
        # Request AI analysis
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            headers=self.headers,
            params={
                "period_type": "monthly",
                "period_value": period,
                "language": "es"
            },
            timeout=120  # AI can take up to 30 seconds
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "analysis" in data, f"No 'analysis' key in response: {data.keys()}"
        analysis = data["analysis"]
        
        # Required sections (original)
        required_sections = [
            "executive_summary",
            "profitability_analysis",
            "returns_analysis",
            "liquidity_analysis",
            "solvency_analysis",
            "recommendations"
        ]
        
        # New sections added in the fix
        new_sections = [
            "income_flow_analysis",
            "trends_analysis"  # Only if multiple periods exist
        ]
        
        print(f"\n✓ AI Analysis sections found: {list(analysis.keys())}")
        
        # Verify required sections
        for section in required_sections:
            assert section in analysis, f"Missing required section: {section}"
            assert analysis[section], f"Section {section} is empty"
            print(f"  ✓ {section}: {analysis[section][:100]}...")
        
        # Verify income_flow_analysis (NEW - main bug fix)
        assert "income_flow_analysis" in analysis, \
            "CRITICAL: income_flow_analysis missing - this was the main bug fix!"
        assert analysis["income_flow_analysis"], "income_flow_analysis is empty"
        print(f"  ✓ income_flow_analysis: {analysis['income_flow_analysis'][:100]}...")
        
        # trends_analysis is optional (only appears when multiple periods exist)
        if "trends_analysis" in analysis:
            print(f"  ✓ trends_analysis: {analysis['trends_analysis'][:100]}...")
        else:
            print(f"  ⓘ trends_analysis not present (requires multiple historical periods)")
        
        # Verify generated_by field
        assert analysis.get("generated_by") in ["AI", "Default"], \
            f"Invalid generated_by: {analysis.get('generated_by')}"
        print(f"  ✓ generated_by: {analysis.get('generated_by')}")
    
    def test_ai_analysis_language_support(self):
        """Test that AI analysis supports multiple languages"""
        periods_response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=self.headers
        )
        periods = periods_response.json()
        if not periods:
            pytest.skip("No periods available")
        
        period = periods[0]["periodo"]
        
        for lang in ["es", "en", "pt"]:
            response = requests.get(
                f"{BASE_URL}/api/financial-statements/ai-analysis",
                headers=self.headers,
                params={
                    "period_type": "monthly",
                    "period_value": period,
                    "language": lang
                },
                timeout=120
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "analysis" in data
            print(f"✓ Language '{lang}' supported - got analysis with {len(data['analysis'].keys())} sections")


class TestPDFExportContent:
    """Tests to verify PDF export includes AI analysis sections
    Note: We can't directly test the PDF content, but we can verify the 
    endpoint provides all necessary data for the PDF export
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_all_data_available_for_pdf_export(self):
        """
        Verify that all data needed for comprehensive PDF export is available:
        - Financial metrics
        - AI analysis with income_flow_analysis
        - Trends data
        """
        # Get periods
        periods_response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=self.headers
        )
        assert periods_response.status_code == 200
        periods = periods_response.json()
        
        if not periods:
            pytest.skip("No periods available")
        
        period = periods[0]["periodo"]
        
        # 1. Verify metrics endpoint
        metrics_response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/{period}",
            headers=self.headers
        )
        assert metrics_response.status_code == 200
        metrics_data = metrics_response.json()
        assert "income_statement" in metrics_data or "metrics" in metrics_data
        print("✓ Metrics data available for PDF")
        
        # 2. Verify trends endpoint
        trends_response = requests.get(
            f"{BASE_URL}/api/financial-statements/trends",
            headers=self.headers
        )
        assert trends_response.status_code == 200
        print("✓ Trends data available for PDF")
        
        # 3. Verify AI analysis includes income_flow_analysis
        ai_response = requests.get(
            f"{BASE_URL}/api/financial-statements/ai-analysis",
            headers=self.headers,
            params={
                "period_type": "monthly",
                "period_value": period,
                "language": "es"
            },
            timeout=120
        )
        assert ai_response.status_code == 200
        ai_data = ai_response.json()
        analysis = ai_data.get("analysis", {})
        
        assert "income_flow_analysis" in analysis, \
            "income_flow_analysis missing from AI analysis - PDF export will be incomplete!"
        print("✓ AI analysis with income_flow_analysis available for PDF")
        
        # 4. Verify Sankey data (used in PDF for income flow visualization)
        sankey_response = requests.get(
            f"{BASE_URL}/api/financial-statements/sankey/{period}",
            headers=self.headers
        )
        assert sankey_response.status_code == 200
        print("✓ Sankey data available for PDF")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
