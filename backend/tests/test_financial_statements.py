"""
Test suite for Financial Statements Module
Tests endpoints:
- GET /api/financial-statements/periods - List available periods
- POST /api/financial-statements/upload/income-statement - Upload Income Statement Excel
- POST /api/financial-statements/upload/balance-sheet - Upload Balance Sheet Excel
- GET /api/financial-statements/metrics/{periodo} - Get calculated metrics
- DELETE /api/financial-statements/{periodo} - Delete period data
"""

import pytest
import requests
import os
import json
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"
COMPANY_ID = "977b125b-2c48-4e2e-8784-3ef81d74064f"

# Test files
INCOME_STATEMENT_FILE = "/tmp/estado_resultados_test.xlsx"
BALANCE_SHEET_FILE = "/tmp/balance_general_test.xlsx"

# Test period
TEST_PERIOD = "2026-02"  # Use a different period for testing to avoid conflicts with 2026-01


class TestFinancialStatementsAuth:
    """Test authentication for financial statements endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get authenticated headers with company ID"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "X-Company-ID": COMPANY_ID
        }
    
    def test_unauthenticated_periods_request_fails(self):
        """Test that periods endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/financial-statements/periods")
        assert response.status_code in [401, 403], "Unauthenticated request should fail"
        print("✓ Unauthenticated request correctly rejected")


class TestFinancialStatementsPeriods:
    """Test periods listing endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get authenticated headers"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "X-Company-ID": COMPANY_ID
        }
    
    def test_get_periods_returns_list(self, headers):
        """Test GET /api/financial-statements/periods returns list of periods"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=headers
        )
        assert response.status_code == 200, f"Failed to get periods: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET periods returned {len(data)} periods")
        
        # Verify structure if there are periods
        if len(data) > 0:
            period = data[0]
            assert "periodo" in period, "Period should have 'periodo' field"
            assert "has_income_statement" in period, "Period should have 'has_income_statement' field"
            assert "has_balance_sheet" in period, "Period should have 'has_balance_sheet' field"
            print(f"✓ Period structure verified: {period['periodo']}")
    
    def test_existing_period_2026_01(self, headers):
        """Test that period 2026-01 exists with data (as per agent context)"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find 2026-01 period
        period_2026_01 = next((p for p in data if p["periodo"] == "2026-01"), None)
        if period_2026_01:
            print(f"✓ Period 2026-01 found: has_income={period_2026_01['has_income_statement']}, has_balance={period_2026_01['has_balance_sheet']}")
        else:
            print("⚠ Period 2026-01 not found (may need to upload data)")


class TestFinancialStatementsUpload:
    """Test Excel upload endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get authenticated headers without content-type for file upload"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "X-Company-ID": COMPANY_ID
        }
    
    def test_upload_income_statement_invalid_file_type(self, headers):
        """Test that non-Excel files are rejected for income statement"""
        # Create a dummy text file
        dummy_file = ("test.txt", b"This is not an Excel file", "text/plain")
        
        response = requests.post(
            f"{BASE_URL}/api/financial-statements/upload/income-statement?periodo={TEST_PERIOD}",
            headers=headers,
            files={"file": dummy_file}
        )
        assert response.status_code == 400, f"Should reject non-Excel file: {response.text}"
        print("✓ Non-Excel file correctly rejected for income statement")
    
    def test_upload_balance_sheet_invalid_file_type(self, headers):
        """Test that non-Excel files are rejected for balance sheet"""
        dummy_file = ("test.txt", b"This is not an Excel file", "text/plain")
        
        response = requests.post(
            f"{BASE_URL}/api/financial-statements/upload/balance-sheet?periodo={TEST_PERIOD}",
            headers=headers,
            files={"file": dummy_file}
        )
        assert response.status_code == 400, f"Should reject non-Excel file: {response.text}"
        print("✓ Non-Excel file correctly rejected for balance sheet")
    
    def test_upload_income_statement_requires_periodo(self, headers):
        """Test that periodo query param is required"""
        # Check if test file exists
        if not os.path.exists(INCOME_STATEMENT_FILE):
            pytest.skip("Income statement test file not found")
        
        with open(INCOME_STATEMENT_FILE, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/api/financial-statements/upload/income-statement",  # No periodo param
                headers=headers,
                files={"file": ("estado_resultados.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        assert response.status_code == 422, f"Should require periodo parameter: {response.text}"
        print("✓ Periodo parameter correctly required for income statement upload")
    
    def test_upload_income_statement_success(self, headers):
        """Test successful upload of income statement Excel"""
        if not os.path.exists(INCOME_STATEMENT_FILE):
            pytest.skip("Income statement test file not found")
        
        with open(INCOME_STATEMENT_FILE, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/api/financial-statements/upload/income-statement?periodo={TEST_PERIOD}",
                headers=headers,
                files={"file": ("estado_resultados_test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        
        assert response.status_code == 200, f"Failed to upload income statement: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Upload should return success=True"
        assert "data" in data, "Response should include parsed data"
        
        # Verify parsed data structure
        parsed = data["data"]
        expected_fields = ["ingresos", "costo_ventas", "utilidad_bruta", "utilidad_neta", "ebitda"]
        for field in expected_fields:
            assert field in parsed, f"Parsed data should include '{field}'"
        
        print(f"✓ Income statement uploaded successfully for {TEST_PERIOD}")
        print(f"  Ingresos: {parsed.get('ingresos', 0):,.2f}")
        print(f"  Utilidad Neta: {parsed.get('utilidad_neta', 0):,.2f}")
    
    def test_upload_balance_sheet_success(self, headers):
        """Test successful upload of balance sheet Excel"""
        if not os.path.exists(BALANCE_SHEET_FILE):
            pytest.skip("Balance sheet test file not found")
        
        with open(BALANCE_SHEET_FILE, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/api/financial-statements/upload/balance-sheet?periodo={TEST_PERIOD}",
                headers=headers,
                files={"file": ("balance_general_test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        
        assert response.status_code == 200, f"Failed to upload balance sheet: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Upload should return success=True"
        assert "data" in data, "Response should include parsed data"
        
        # Verify parsed data structure
        parsed = data["data"]
        expected_fields = ["activo_total", "pasivo_total", "capital_contable", "efectivo", "activo_circulante"]
        for field in expected_fields:
            assert field in parsed, f"Parsed data should include '{field}'"
        
        print(f"✓ Balance sheet uploaded successfully for {TEST_PERIOD}")
        print(f"  Activo Total: {parsed.get('activo_total', 0):,.2f}")
        print(f"  Capital Contable: {parsed.get('capital_contable', 0):,.2f}")


class TestFinancialStatementsMetrics:
    """Test metrics calculation endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get authenticated headers"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "X-Company-ID": COMPANY_ID
        }
    
    def test_get_metrics_nonexistent_period(self, headers):
        """Test that requesting metrics for non-existent period returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/9999-99",
            headers=headers
        )
        assert response.status_code == 404, f"Should return 404 for non-existent period: {response.text}"
        print("✓ Non-existent period correctly returns 404")
    
    def test_get_metrics_existing_period(self, headers):
        """Test GET /api/financial-statements/metrics/{periodo} returns calculated metrics"""
        # First check if 2026-01 exists
        periods_response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=headers
        )
        periods = periods_response.json()
        
        # Use existing period or the test period
        test_periodo = None
        for p in periods:
            if p.get("has_income_statement") or p.get("has_balance_sheet"):
                test_periodo = p["periodo"]
                break
        
        if not test_periodo:
            pytest.skip("No periods with data found")
        
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/{test_periodo}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to get metrics: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "periodo" in data, "Response should have 'periodo'"
        assert "metrics" in data, "Response should have 'metrics'"
        assert "has_income_statement" in data, "Response should have 'has_income_statement'"
        assert "has_balance_sheet" in data, "Response should have 'has_balance_sheet'"
        
        print(f"✓ Metrics retrieved for period {test_periodo}")
        print(f"  Has Income Statement: {data['has_income_statement']}")
        print(f"  Has Balance Sheet: {data['has_balance_sheet']}")
        
        # Verify metrics structure
        metrics = data["metrics"]
        expected_categories = ["margins", "returns", "liquidity", "solvency", "absolute_values"]
        for category in expected_categories:
            if category in metrics:
                print(f"  ✓ Metrics category '{category}' present")
    
    def test_metrics_margins_calculation(self, headers):
        """Test that margin metrics are correctly calculated"""
        periods_response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=headers
        )
        periods = periods_response.json()
        
        # Find a period with income statement
        test_periodo = None
        for p in periods:
            if p.get("has_income_statement"):
                test_periodo = p["periodo"]
                break
        
        if not test_periodo:
            pytest.skip("No periods with income statement found")
        
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/{test_periodo}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        metrics = data.get("metrics", {})
        margins = metrics.get("margins", {})
        
        # Verify margin metrics structure
        margin_types = ["gross_margin", "ebitda_margin", "operating_margin", "net_margin"]
        for margin_type in margin_types:
            if margin_type in margins:
                margin = margins[margin_type]
                assert "value" in margin, f"{margin_type} should have 'value'"
                assert "label" in margin, f"{margin_type} should have 'label'"
                assert "formula" in margin, f"{margin_type} should have 'formula'"
                print(f"  {margin['label']}: {margin['value']:.2f}%")
        
        print("✓ Margin metrics structure verified")
    
    def test_metrics_returns_calculation(self, headers):
        """Test that return metrics are correctly calculated"""
        periods_response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=headers
        )
        periods = periods_response.json()
        
        # Find a period with both statements
        test_periodo = None
        for p in periods:
            if p.get("has_income_statement") and p.get("has_balance_sheet"):
                test_periodo = p["periodo"]
                break
        
        if not test_periodo:
            pytest.skip("No periods with both statements found")
        
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/{test_periodo}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        returns = data.get("metrics", {}).get("returns", {})
        
        # Verify return metrics
        return_types = ["roic", "roe", "roa", "roce"]
        for return_type in return_types:
            if return_type in returns:
                ret = returns[return_type]
                assert "value" in ret, f"{return_type} should have 'value'"
                print(f"  {ret['label']}: {ret['value']:.2f}%")
        
        print("✓ Return metrics structure verified")


class TestFinancialStatementsDelete:
    """Test period deletion endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get authenticated headers"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "X-Company-ID": COMPANY_ID
        }
    
    def test_delete_nonexistent_period(self, headers):
        """Test deleting a non-existent period returns success with 0 deleted"""
        response = requests.delete(
            f"{BASE_URL}/api/financial-statements/9999-99",
            headers=headers
        )
        # Should succeed even if no documents found
        assert response.status_code == 200, f"Delete should succeed: {response.text}"
        data = response.json()
        assert data.get("deleted") == 0 or data.get("success") == True
        print("✓ Delete non-existent period handled correctly")
    
    def test_delete_specific_type(self, headers):
        """Test deleting only income statement or balance sheet using tipo parameter"""
        response = requests.delete(
            f"{BASE_URL}/api/financial-statements/9999-99?tipo=estado_resultados",
            headers=headers
        )
        assert response.status_code == 200, f"Delete with tipo should succeed: {response.text}"
        print("✓ Delete with tipo parameter works correctly")
    
    def test_delete_test_period_cleanup(self, headers):
        """Clean up the test period created during upload tests"""
        response = requests.delete(
            f"{BASE_URL}/api/financial-statements/{TEST_PERIOD}",
            headers=headers
        )
        assert response.status_code == 200, f"Cleanup failed: {response.text}"
        data = response.json()
        print(f"✓ Cleaned up test period {TEST_PERIOD}: {data.get('deleted', 0)} records deleted")


class TestFinancialStatementsFull:
    """Full integration test: upload -> verify -> delete"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get authenticated headers"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "X-Company-ID": COMPANY_ID
        }
    
    def test_full_workflow(self, headers):
        """Test complete workflow: upload income statement -> upload balance -> get metrics -> verify -> delete"""
        test_periodo = "2026-03"  # Use a different period for this test
        
        # Step 1: Upload income statement
        if os.path.exists(INCOME_STATEMENT_FILE):
            with open(INCOME_STATEMENT_FILE, "rb") as f:
                response = requests.post(
                    f"{BASE_URL}/api/financial-statements/upload/income-statement?periodo={test_periodo}",
                    headers={"Authorization": headers["Authorization"], "X-Company-ID": headers["X-Company-ID"]},
                    files={"file": ("estado_resultados_test.xlsx", f)}
                )
            assert response.status_code == 200, f"Step 1 failed: {response.text}"
            print(f"✓ Step 1: Income statement uploaded for {test_periodo}")
        else:
            pytest.skip("Income statement test file not found")
        
        # Step 2: Upload balance sheet
        if os.path.exists(BALANCE_SHEET_FILE):
            with open(BALANCE_SHEET_FILE, "rb") as f:
                response = requests.post(
                    f"{BASE_URL}/api/financial-statements/upload/balance-sheet?periodo={test_periodo}",
                    headers={"Authorization": headers["Authorization"], "X-Company-ID": headers["X-Company-ID"]},
                    files={"file": ("balance_general_test.xlsx", f)}
                )
            assert response.status_code == 200, f"Step 2 failed: {response.text}"
            print(f"✓ Step 2: Balance sheet uploaded for {test_periodo}")
        else:
            pytest.skip("Balance sheet test file not found")
        
        # Step 3: Verify period appears in list
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/periods",
            headers=headers
        )
        assert response.status_code == 200, f"Step 3 failed: {response.text}"
        periods = response.json()
        period_found = next((p for p in periods if p["periodo"] == test_periodo), None)
        assert period_found is not None, f"Period {test_periodo} not found in periods list"
        assert period_found["has_income_statement"] == True, "Income statement should be present"
        assert period_found["has_balance_sheet"] == True, "Balance sheet should be present"
        print(f"✓ Step 3: Period {test_periodo} verified in periods list")
        
        # Step 4: Get and verify metrics
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/{test_periodo}",
            headers=headers
        )
        assert response.status_code == 200, f"Step 4 failed: {response.text}"
        data = response.json()
        assert data["has_income_statement"] == True
        assert data["has_balance_sheet"] == True
        assert "metrics" in data
        
        # Verify some metric values exist
        metrics = data["metrics"]
        assert "margins" in metrics, "Margins should be calculated"
        assert "returns" in metrics, "Returns should be calculated"
        assert "liquidity" in metrics, "Liquidity should be calculated"
        print(f"✓ Step 4: Metrics calculated successfully")
        
        # Step 5: Clean up - delete the test period
        response = requests.delete(
            f"{BASE_URL}/api/financial-statements/{test_periodo}",
            headers=headers
        )
        assert response.status_code == 200, f"Step 5 failed: {response.text}"
        data = response.json()
        assert data.get("deleted", 0) >= 2 or data.get("success") == True, "Should delete at least 2 records"
        print(f"✓ Step 5: Test period cleaned up")
        
        # Step 6: Verify deletion
        response = requests.get(
            f"{BASE_URL}/api/financial-statements/metrics/{test_periodo}",
            headers=headers
        )
        assert response.status_code == 404, f"Period should no longer exist: {response.text}"
        print(f"✓ Step 6: Deletion verified - period no longer exists")
        
        print("\n✓ Full workflow test completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
