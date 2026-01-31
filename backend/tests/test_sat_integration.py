"""
SAT Integration API Tests
Tests for SAT credential management and CFDI sync endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"
TEST_RFC = "XAXX010101000"
TEST_CIEC = "TestCiec123"


class TestSATIntegration:
    """SAT Integration endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Auth failed: {response.text}"
        token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        # Cleanup - delete any test credentials
        try:
            self.session.delete(f"{BASE_URL}/api/sat/credentials")
        except:
            pass
    
    def test_sat_status_no_credentials(self):
        """Test GET /api/sat/status returns unconfigured when no credentials"""
        # First ensure no credentials exist
        self.session.delete(f"{BASE_URL}/api/sat/credentials")
        
        response = self.session.get(f"{BASE_URL}/api/sat/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "configured" in data
        assert data["configured"] == False
        assert "message" in data
        assert data["last_sync"] is None
    
    def test_sat_comprobante_types(self):
        """Test GET /api/sat/comprobante-types returns list of CFDI types"""
        response = self.session.get(f"{BASE_URL}/api/sat/comprobante-types")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5  # At least 5 types: todos, ingreso, egreso, pago, nomina
        
        # Verify structure
        for item in data:
            assert "value" in item
            assert "label" in item
        
        # Verify expected types exist
        values = [item["value"] for item in data]
        assert "todos" in values
        assert "ingreso" in values
        assert "egreso" in values
        assert "pago" in values
        assert "nomina" in values
    
    def test_save_sat_credentials_success(self):
        """Test POST /api/sat/credentials saves credentials successfully"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": TEST_CIEC
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["rfc"] == TEST_RFC
        assert "message" in data
        assert "guardadas" in data["message"].lower()
    
    def test_save_sat_credentials_invalid_rfc(self):
        """Test POST /api/sat/credentials rejects invalid RFC"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": "ABC",  # Too short
            "ciec": TEST_CIEC
        })
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        assert "rfc" in data["detail"].lower() or "inválido" in data["detail"].lower()
    
    def test_save_sat_credentials_invalid_ciec(self):
        """Test POST /api/sat/credentials rejects invalid CIEC"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": "short"  # Too short (less than 8 chars)
        })
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        assert "ciec" in data["detail"].lower() or "inválid" in data["detail"].lower()
    
    def test_sat_status_with_credentials(self):
        """Test GET /api/sat/status returns configured after saving credentials"""
        # First save credentials
        save_response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": TEST_CIEC
        })
        assert save_response.status_code == 200
        
        # Then check status
        response = self.session.get(f"{BASE_URL}/api/sat/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["configured"] == True
        assert data["rfc"] == TEST_RFC
        assert data["status"] == "active"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_delete_sat_credentials_success(self):
        """Test DELETE /api/sat/credentials removes credentials"""
        # First save credentials
        self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": TEST_CIEC
        })
        
        # Delete credentials
        response = self.session.delete(f"{BASE_URL}/api/sat/credentials")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "eliminadas" in data["message"].lower()
        
        # Verify status shows unconfigured
        status_response = self.session.get(f"{BASE_URL}/api/sat/status")
        status_data = status_response.json()
        assert status_data["configured"] == False
    
    def test_delete_sat_credentials_not_found(self):
        """Test DELETE /api/sat/credentials returns 404 when no credentials exist"""
        # Ensure no credentials exist
        self.session.delete(f"{BASE_URL}/api/sat/credentials")
        
        # Try to delete again
        response = self.session.delete(f"{BASE_URL}/api/sat/credentials")
        assert response.status_code == 404
    
    def test_sat_credentials_update_existing(self):
        """Test POST /api/sat/credentials updates existing credentials"""
        # Save initial credentials
        self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": TEST_CIEC
        })
        
        # Update with new RFC
        new_rfc = "XEXX010101000"
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": new_rfc,
            "ciec": "NewCiec12345"
        })
        assert response.status_code == 200
        
        # Verify update
        status_response = self.session.get(f"{BASE_URL}/api/sat/status")
        status_data = status_response.json()
        assert status_data["rfc"] == new_rfc
    
    def test_sat_status_requires_auth(self):
        """Test GET /api/sat/status requires authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/sat/status")
        assert response.status_code in [401, 403]
    
    def test_sat_credentials_requires_auth(self):
        """Test POST /api/sat/credentials requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        response = no_auth_session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": TEST_CIEC
        })
        assert response.status_code in [401, 403]


class TestSATCredentialValidation:
    """Tests for SAT credential validation edge cases"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/sat/credentials")
        except:
            pass
    
    def test_rfc_12_characters_valid(self):
        """Test RFC with 12 characters (persona moral) is valid"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": "ABC123456789",  # 12 chars
            "ciec": "TestCiec123"
        })
        assert response.status_code == 200
    
    def test_rfc_13_characters_valid(self):
        """Test RFC with 13 characters (persona física) is valid"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": "XAXX010101000",  # 13 chars
            "ciec": "TestCiec123"
        })
        assert response.status_code == 200
    
    def test_rfc_uppercase_conversion(self):
        """Test RFC is converted to uppercase"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": "xaxx010101000",  # lowercase
            "ciec": "TestCiec123"
        })
        assert response.status_code == 200
        
        status_response = self.session.get(f"{BASE_URL}/api/sat/status")
        assert status_response.json()["rfc"] == "XAXX010101000"  # Should be uppercase
    
    def test_ciec_minimum_length(self):
        """Test CIEC must be at least 8 characters"""
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": "1234567"  # 7 chars - too short
        })
        assert response.status_code == 400
        
        # 8 chars should work
        response = self.session.post(f"{BASE_URL}/api/sat/credentials", json={
            "rfc": TEST_RFC,
            "ciec": "12345678"  # 8 chars - valid
        })
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
