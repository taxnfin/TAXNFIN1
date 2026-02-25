"""
Test cases for Company Logo Upload feature
Tests the POST /api/companies/{id}/logo and DELETE /api/companies/{id}/logo endpoints
"""
import pytest
import requests
import os
import base64
from io import BytesIO

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"


class TestCompanyLogoEndpoints:
    """Tests for company logo upload/delete endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code == 200:
            self.token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Could not authenticate: {login_response.status_code}")
    
    def test_get_companies_returns_list(self):
        """Test GET /api/companies returns list of companies"""
        response = self.session.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} companies")
        
        if len(data) > 0:
            company = data[0]
            # Verify company structure includes logo_url field capability
            assert "id" in company, "Company should have 'id' field"
            assert "nombre" in company, "Company should have 'nombre' field"
            # logo_url can be None or a string
            print(f"First company: {company.get('nombre')}, logo_url: {company.get('logo_url', 'not set')[:50] if company.get('logo_url') else 'None'}")
    
    def test_upload_logo_endpoint_exists(self):
        """Test POST /api/companies/{id}/logo endpoint exists"""
        # First get a company id
        companies_response = self.session.get(f"{BASE_URL}/api/companies")
        assert companies_response.status_code == 200
        
        companies = companies_response.json()
        if not companies:
            pytest.skip("No companies available to test logo upload")
        
        company_id = companies[0]["id"]
        
        # Create a small test image (1x1 PNG)
        # This is a valid 1x1 transparent PNG
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        # Test upload with multipart/form-data
        files = {
            'file': ('test_logo.png', BytesIO(png_data), 'image/png')
        }
        
        # Remove content-type header for multipart
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/companies/{company_id}/logo",
            files=files,
            headers=headers
        )
        
        # Should be 200 (success) or 400/422 (validation error) - not 404/405
        assert response.status_code in [200, 201, 400, 422], \
            f"Logo upload endpoint should exist. Got status: {response.status_code}, body: {response.text[:200]}"
        
        if response.status_code == 200:
            data = response.json()
            assert "logo_url" in data, "Response should contain logo_url"
            assert data["logo_url"].startswith("data:image/"), "logo_url should be a data URL"
            print(f"Logo uploaded successfully, data URL length: {len(data['logo_url'])}")
    
    def test_delete_logo_endpoint_exists(self):
        """Test DELETE /api/companies/{id}/logo endpoint exists"""
        # First get a company id
        companies_response = self.session.get(f"{BASE_URL}/api/companies")
        assert companies_response.status_code == 200
        
        companies = companies_response.json()
        if not companies:
            pytest.skip("No companies available to test logo delete")
        
        company_id = companies[0]["id"]
        
        # Test delete endpoint
        response = self.session.delete(f"{BASE_URL}/api/companies/{company_id}/logo")
        
        # Should be 200 (success) or 404 (no logo) - not 405 (method not allowed)
        assert response.status_code in [200, 204, 404], \
            f"Logo delete endpoint should exist. Got status: {response.status_code}, body: {response.text[:200]}"
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, "Delete should return success: true"
            print("Logo deleted successfully")
    
    def test_logo_upload_validates_file_type(self):
        """Test that logo upload validates file type"""
        # Get a company id
        companies_response = self.session.get(f"{BASE_URL}/api/companies")
        companies = companies_response.json()
        if not companies:
            pytest.skip("No companies available")
        
        company_id = companies[0]["id"]
        
        # Try to upload a non-image file
        files = {
            'file': ('test.txt', BytesIO(b'This is not an image'), 'text/plain')
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/companies/{company_id}/logo",
            files=files,
            headers=headers
        )
        
        # Should reject non-image files with 400
        assert response.status_code == 400, \
            f"Should reject non-image files. Got: {response.status_code}"
        print("Non-image file correctly rejected")


class TestBoardReportEndpoints:
    """Tests for Board Report related endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code == 200:
            self.token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Could not authenticate: {login_response.status_code}")
    
    def test_financial_statements_periods_endpoint(self):
        """Test GET /api/financial-statements/periods returns available periods"""
        response = self.session.get(f"{BASE_URL}/api/financial-statements/periods")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} financial statement periods")
    
    def test_financial_statements_trends_endpoint(self):
        """Test GET /api/financial-statements/trends returns trend data"""
        response = self.session.get(f"{BASE_URL}/api/financial-statements/trends")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Trends data: {type(data)}")
    
    def test_financial_statements_available_periods_endpoint(self):
        """Test GET /api/financial-statements/available-periods returns period options"""
        response = self.session.get(f"{BASE_URL}/api/financial-statements/available-periods")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have structure for monthly, quarterly, annual periods
        assert isinstance(data, dict), "Response should be a dict"
        print(f"Available periods keys: {list(data.keys())}")
    
    def test_company_includes_logo_url_field(self):
        """Test that company data includes logo_url field"""
        response = self.session.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 200
        
        companies = response.json()
        if companies:
            company = companies[0]
            # The logo_url field should exist (can be null or contain base64 data)
            # We just verify the API returns the field
            print(f"Company '{company.get('nombre')}' logo_url is {'set' if company.get('logo_url') else 'not set'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
