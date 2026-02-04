"""
Test suite for Alegra Integration API endpoints
Tests: /api/alegra/status, /api/alegra/test-connection, /api/alegra/save-credentials,
       /api/alegra/sync/contacts, /api/alegra/sync/invoices, /api/alegra/sync/bills,
       /api/alegra/sync/payments, /api/alegra/disconnect
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"
ALEGRA_EMAIL = "karina.villafuerte@ortech.com.mx"
ALEGRA_TOKEN = "91c010d0bed913f902a1"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API requests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with authentication token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestAlegraStatus:
    """Tests for GET /api/alegra/status endpoint"""
    
    def test_status_requires_auth(self):
        """Test that status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/alegra/status")
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_status_returns_connection_info(self, auth_headers):
        """Test that status returns connection information"""
        response = requests.get(
            f"{BASE_URL}/api/alegra/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "connected" in data
        assert isinstance(data["connected"], bool)
        
        if data["connected"]:
            assert "email" in data
            assert "connected_at" in data


class TestAlegraTestConnection:
    """Tests for POST /api/alegra/test-connection endpoint"""
    
    def test_test_connection_requires_auth(self):
        """Test that test-connection endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/test-connection",
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_test_connection_with_valid_credentials(self, auth_headers):
        """Test connection with valid Alegra credentials"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/test-connection",
            headers=auth_headers,
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "message" in data
        assert "Conexión exitosa" in data["message"]
    
    def test_test_connection_with_invalid_credentials(self, auth_headers):
        """Test connection with invalid Alegra credentials"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/test-connection",
            headers=auth_headers,
            json={"email": "invalid@test.com", "token": "invalid_token"}
        )
        assert response.status_code == 200  # Returns 200 with success=false
        data = response.json()
        
        assert "success" in data
        assert data["success"] == False
    
    def test_test_connection_missing_fields(self, auth_headers):
        """Test connection with missing required fields"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/test-connection",
            headers=auth_headers,
            json={"email": ALEGRA_EMAIL}  # Missing token
        )
        assert response.status_code == 422, "Should return validation error"


class TestAlegraSaveCredentials:
    """Tests for POST /api/alegra/save-credentials endpoint"""
    
    def test_save_credentials_requires_auth(self):
        """Test that save-credentials endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/save-credentials",
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_save_credentials_with_valid_data(self, auth_headers):
        """Test saving valid Alegra credentials"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/save-credentials",
            headers=auth_headers,
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "message" in data
    
    def test_save_credentials_with_invalid_data(self, auth_headers):
        """Test saving invalid Alegra credentials"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/save-credentials",
            headers=auth_headers,
            json={"email": "invalid@test.com", "token": "invalid_token"}
        )
        assert response.status_code == 400, "Should reject invalid credentials"


class TestAlegraSyncContacts:
    """Tests for POST /api/alegra/sync/contacts endpoint"""
    
    def test_sync_contacts_requires_auth(self):
        """Test that sync contacts endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/alegra/sync/contacts")
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_sync_contacts_when_connected(self, auth_headers):
        """Test syncing contacts when Alegra is connected"""
        # First check if connected
        status_response = requests.get(
            f"{BASE_URL}/api/alegra/status",
            headers=auth_headers
        )
        if not status_response.json().get("connected"):
            pytest.skip("Alegra not connected - skipping sync test")
        
        # Note: This may hit rate limits or take time
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/contacts",
            headers=auth_headers,
            timeout=120
        )
        
        # Accept 200 (success), 400 (rate limit error from Alegra), or 429 (rate limit)
        # Alegra API returns 429 which gets wrapped as 400 by our error handler
        assert response.status_code in [200, 400, 429], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "stats" in data
            assert "total" in data["stats"]
        elif response.status_code == 400:
            # Rate limit error from Alegra API
            data = response.json()
            assert "429" in str(data.get("detail", "")) or "rate" in str(data.get("detail", "")).lower()


class TestAlegraSyncInvoices:
    """Tests for POST /api/alegra/sync/invoices endpoint (CxC)"""
    
    def test_sync_invoices_requires_auth(self):
        """Test that sync invoices endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/alegra/sync/invoices")
        assert response.status_code in [401, 403], "Should require authentication"
    
    @pytest.mark.skip(reason="Sync invoices can take several minutes due to ~687 invoices")
    def test_sync_invoices_when_connected(self, auth_headers):
        """Test syncing invoices when Alegra is connected"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/invoices",
            headers=auth_headers,
            timeout=300
        )
        assert response.status_code in [200, 429]


class TestAlegraSyncBills:
    """Tests for POST /api/alegra/sync/bills endpoint (CxP)"""
    
    def test_sync_bills_requires_auth(self):
        """Test that sync bills endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/alegra/sync/bills")
        assert response.status_code in [401, 403], "Should require authentication"
    
    @pytest.mark.skip(reason="Sync bills can take several minutes due to ~2058 bills")
    def test_sync_bills_when_connected(self, auth_headers):
        """Test syncing bills when Alegra is connected"""
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/bills",
            headers=auth_headers,
            timeout=300
        )
        assert response.status_code in [200, 429]


class TestAlegraSyncPayments:
    """Tests for POST /api/alegra/sync/payments endpoint"""
    
    def test_sync_payments_requires_auth(self):
        """Test that sync payments endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/alegra/sync/payments")
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_sync_payments_when_connected(self, auth_headers):
        """Test syncing payments when Alegra is connected"""
        status_response = requests.get(
            f"{BASE_URL}/api/alegra/status",
            headers=auth_headers
        )
        if not status_response.json().get("connected"):
            pytest.skip("Alegra not connected - skipping sync test")
        
        response = requests.post(
            f"{BASE_URL}/api/alegra/sync/payments",
            headers=auth_headers,
            timeout=120
        )
        
        assert response.status_code in [200, 429]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "stats" in data


class TestAlegraDisconnect:
    """Tests for DELETE /api/alegra/disconnect endpoint"""
    
    def test_disconnect_requires_auth(self):
        """Test that disconnect endpoint requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/alegra/disconnect")
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_disconnect_and_reconnect(self, auth_headers):
        """Test disconnecting and reconnecting Alegra"""
        # First check current status
        status_response = requests.get(
            f"{BASE_URL}/api/alegra/status",
            headers=auth_headers
        )
        initial_status = status_response.json()
        
        if not initial_status.get("connected"):
            # Connect first - may fail due to rate limiting
            connect_response = requests.post(
                f"{BASE_URL}/api/alegra/save-credentials",
                headers=auth_headers,
                json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
            )
            if connect_response.status_code == 400:
                pytest.skip("Alegra API rate limited - skipping disconnect test")
        
        # Disconnect
        disconnect_response = requests.delete(
            f"{BASE_URL}/api/alegra/disconnect",
            headers=auth_headers
        )
        assert disconnect_response.status_code == 200
        data = disconnect_response.json()
        assert data.get("success") == True
        
        # Verify disconnected
        status_after = requests.get(
            f"{BASE_URL}/api/alegra/status",
            headers=auth_headers
        )
        assert status_after.json().get("connected") == False
        
        # Wait a bit before reconnecting to avoid rate limits
        time.sleep(2)
        
        # Reconnect for other tests - may fail due to rate limiting
        reconnect_response = requests.post(
            f"{BASE_URL}/api/alegra/save-credentials",
            headers=auth_headers,
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        # Accept 200 (success) or 400 (rate limited)
        assert reconnect_response.status_code in [200, 400], f"Unexpected: {reconnect_response.status_code}"
        
        if reconnect_response.status_code == 200:
            # Verify reconnected
            final_status = requests.get(
                f"{BASE_URL}/api/alegra/status",
                headers=auth_headers
            )
            assert final_status.json().get("connected") == True


class TestAlegraIntegrationFlow:
    """End-to-end integration tests for Alegra workflow"""
    
    def test_full_connection_flow(self, auth_headers):
        """Test the complete connection flow: test -> save -> status"""
        # Wait a bit to avoid rate limits from previous tests
        time.sleep(3)
        
        # Step 1: Test connection
        test_response = requests.post(
            f"{BASE_URL}/api/alegra/test-connection",
            headers=auth_headers,
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        assert test_response.status_code == 200
        test_data = test_response.json()
        
        # May fail due to rate limiting
        if not test_data.get("success"):
            if "429" in str(test_data.get("message", "")) or "rate" in str(test_data.get("message", "")).lower():
                pytest.skip("Alegra API rate limited - skipping integration flow test")
        
        assert test_data.get("success") == True
        
        # Step 2: Save credentials
        save_response = requests.post(
            f"{BASE_URL}/api/alegra/save-credentials",
            headers=auth_headers,
            json={"email": ALEGRA_EMAIL, "token": ALEGRA_TOKEN}
        )
        # May be rate limited
        if save_response.status_code == 400:
            pytest.skip("Alegra API rate limited during save - skipping")
        
        assert save_response.status_code == 200
        assert save_response.json().get("success") == True
        
        # Step 3: Verify status
        status_response = requests.get(
            f"{BASE_URL}/api/alegra/status",
            headers=auth_headers
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data.get("connected") == True
        assert status_data.get("email") == ALEGRA_EMAIL


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
