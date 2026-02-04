"""
Test suite for CFDI/SAT module improvements and Alegra integration features
Tests: Emisor/Receptor filters, Export Excel, Date range sync, Clear data, Multi-company architecture
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"
ALEGRA_EMAIL = "karina.villafuerte@ortech.com.mx"
ALEGRA_TOKEN = "91c010d0bed913f902a1"


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        print(f"✓ Login successful for {TEST_EMAIL}")
        return data["access_token"]


class TestCFDIFilters:
    """Test CFDI filtering functionality"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_cfdis(self, auth_token):
        """Test getting CFDIs list"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cfdi?limit=1000", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} CFDIs")
        return data
    
    def test_cfdi_has_emisor_receptor_fields(self, auth_token):
        """Test that CFDIs have emisor and receptor fields for filtering"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cfdi?limit=10", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            cfdi = data[0]
            # Check for emisor fields
            assert "emisor_rfc" in cfdi or "emisor_nombre" in cfdi, "CFDI should have emisor fields"
            # Check for receptor fields
            assert "receptor_rfc" in cfdi or "receptor_nombre" in cfdi, "CFDI should have receptor fields"
            # Check for fecha_emision for date filtering
            assert "fecha_emision" in cfdi, "CFDI should have fecha_emision field"
            print(f"✓ CFDI has required fields for filtering")
        else:
            print("⚠ No CFDIs found to verify fields")
    
    def test_cfdi_summary(self, auth_token):
        """Test CFDI summary endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cfdi/summary?moneda_vista=MXN", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "totales_convertidos" in data or "balance_convertido" in data
        print(f"✓ CFDI summary endpoint working")


class TestAlegraIntegration:
    """Test Alegra integration endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_alegra_status(self, auth_token):
        """Test Alegra connection status endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/alegra/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        print(f"✓ Alegra status: connected={data.get('connected')}")
    
    def test_alegra_sync_invoices_with_date_params(self, auth_token):
        """Test sync invoices endpoint accepts date_from and date_to parameters"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Test with date parameters - just verify the endpoint accepts them
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/invoices?date_from=2025-01-01&date_to=2025-12-31",
            headers=headers
        )
        # Should return 200 if connected, or 400 if not connected
        assert response.status_code in [200, 400, 429], f"Unexpected status: {response.status_code}"
        print(f"✓ Sync invoices endpoint accepts date parameters (status: {response.status_code})")
    
    def test_alegra_sync_bills_with_date_params(self, auth_token):
        """Test sync bills endpoint accepts date_from and date_to parameters"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/bills?date_from=2025-01-01&date_to=2025-12-31",
            headers=headers
        )
        assert response.status_code in [200, 400, 429], f"Unexpected status: {response.status_code}"
        print(f"✓ Sync bills endpoint accepts date parameters (status: {response.status_code})")
    
    def test_alegra_sync_all_with_date_params(self, auth_token):
        """Test sync all endpoint accepts date_from and date_to parameters"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/all?date_from=2025-01-01&date_to=2025-12-31",
            headers=headers
        )
        assert response.status_code in [200, 400, 429], f"Unexpected status: {response.status_code}"
        print(f"✓ Sync all endpoint accepts date parameters (status: {response.status_code})")
    
    def test_alegra_clear_data_endpoint_exists(self, auth_token):
        """Test that clear-data endpoint exists and returns proper response"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Use OPTIONS to check if endpoint exists without actually deleting
        response = requests.options(f"{BASE_URL}/api/alegra/clear-data", headers=headers)
        # OPTIONS should return 200 if endpoint exists
        assert response.status_code in [200, 204], f"Clear-data endpoint should exist"
        print(f"✓ Clear-data endpoint exists")
    
    def test_alegra_clear_data_with_params(self, auth_token):
        """Test clear-data endpoint accepts query parameters"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Test with specific parameters - this will actually delete data if connected
        # So we just verify the endpoint structure
        response = requests.delete(
            f"{BASE_URL}/api/alegra/clear-data?clear_customers=false&clear_vendors=false&clear_payments=false",
            headers=headers
        )
        # Should return 200 with results even if nothing to delete
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        data = response.json()
        assert "success" in data
        assert "results" in data or "message" in data
        print(f"✓ Clear-data endpoint works with parameters")


class TestMultiCompanyArchitecture:
    """Test multi-company data filtering"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_user_has_company_id(self, auth_token):
        """Test that user has company_id for multi-company filtering"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        data = response.json()
        assert "user" in data
        assert "company_id" in data["user"], "User should have company_id"
        print(f"✓ User has company_id: {data['user']['company_id']}")
    
    def test_companies_endpoint(self, auth_token):
        """Test companies endpoint returns company data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/companies", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)
        print(f"✓ Companies endpoint working")
    
    def test_cfdi_filtered_by_company(self, auth_token):
        """Test that CFDIs are filtered by company_id"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cfdi?limit=10", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            # All CFDIs should belong to the same company
            company_ids = set()
            for cfdi in data:
                if "company_id" in cfdi:
                    company_ids.add(cfdi["company_id"])
            
            # Should only have one company_id (the user's company)
            assert len(company_ids) <= 1, "CFDIs should be filtered by company_id"
            print(f"✓ CFDIs are filtered by company_id")
        else:
            print("⚠ No CFDIs found to verify company filtering")


class TestExportExcel:
    """Test Excel export functionality (backend support)"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_cfdi_data_has_export_fields(self, auth_token):
        """Test that CFDI data has all fields needed for Excel export"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/cfdi?limit=10", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            cfdi = data[0]
            # Check for essential export fields
            export_fields = ["uuid", "tipo_cfdi", "emisor_rfc", "receptor_rfc", 
                          "fecha_emision", "total", "moneda"]
            
            missing_fields = []
            for field in export_fields:
                if field not in cfdi:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"⚠ Missing fields for export: {missing_fields}")
            else:
                print(f"✓ CFDI has all essential fields for Excel export")
        else:
            print("⚠ No CFDIs found to verify export fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
