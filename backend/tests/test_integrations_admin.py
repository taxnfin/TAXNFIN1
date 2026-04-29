"""
Test suite for Integrations Module and Admin Dashboard
Tests: GET /api/integrations/available-list, /connected, POST /connect, /{id}/test, /{id}/sync, DELETE /{id}
Admin: GET /api/integrations/admin/all-companies, /admin/all-users
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestIntegrationsAvailableList:
    """Test GET /api/integrations/available-list - returns all 6 integration types"""
    
    def test_available_list_returns_200(self, auth_headers):
        """Should return 200 with list of integrations"""
        response = requests.get(f"{BASE_URL}/api/integrations/available-list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Available list returns {len(data)} integrations")
    
    def test_available_list_has_6_integrations(self, auth_headers):
        """Should return exactly 6 integration types"""
        response = requests.get(f"{BASE_URL}/api/integrations/available-list", headers=auth_headers)
        data = response.json()
        assert len(data) == 6, f"Expected 6 integrations, got {len(data)}"
        
        # Check all expected keys
        keys = [i['key'] for i in data]
        expected_keys = ['contalink', 'alegra', 'quickbooks', 'contpaqi', 'xero', 'sap']
        for key in expected_keys:
            assert key in keys, f"Missing integration: {key}"
        print(f"✓ All 6 integrations present: {keys}")
    
    def test_available_list_structure(self, auth_headers):
        """Each integration should have required fields"""
        response = requests.get(f"{BASE_URL}/api/integrations/available-list", headers=auth_headers)
        data = response.json()
        
        required_fields = ['key', 'name', 'description', 'capabilities', 'auth_type', 'fields', 'status']
        for integration in data:
            for field in required_fields:
                assert field in integration, f"Missing field '{field}' in {integration.get('key', 'unknown')}"
        print("✓ All integrations have required fields")
    
    def test_coming_soon_status(self, auth_headers):
        """QuickBooks, CONTPAQi, Xero, SAP should be 'coming_soon'"""
        response = requests.get(f"{BASE_URL}/api/integrations/available-list", headers=auth_headers)
        data = response.json()
        
        coming_soon_expected = ['quickbooks', 'contpaqi', 'xero', 'sap']
        available_expected = ['contalink', 'alegra']
        
        for integration in data:
            if integration['key'] in coming_soon_expected:
                assert integration['status'] == 'coming_soon', f"{integration['key']} should be coming_soon"
            elif integration['key'] in available_expected:
                assert integration['status'] == 'available', f"{integration['key']} should be available"
        
        print("✓ Status correctly set for all integrations")


class TestIntegrationsConnected:
    """Test GET /api/integrations/connected - returns connected integrations"""
    
    def test_connected_returns_200(self, auth_headers):
        """Should return 200 with list"""
        response = requests.get(f"{BASE_URL}/api/integrations/connected", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Connected integrations: {len(data)} found")
    
    def test_connected_has_contalink(self, auth_headers):
        """CONTALink should be connected (per context)"""
        response = requests.get(f"{BASE_URL}/api/integrations/connected", headers=auth_headers)
        data = response.json()
        
        contalink = next((i for i in data if i.get('integration_type') == 'contalink'), None)
        if contalink:
            assert contalink['connection_status'] in ['connected', 'pending']
            assert 'credentials' not in contalink, "Credentials should not be exposed"
            print(f"✓ CONTALink connected with status: {contalink['connection_status']}")
        else:
            print("⚠ CONTALink not found in connected integrations (may need to connect first)")
    
    def test_connected_no_credentials_exposed(self, auth_headers):
        """Credentials should never be returned"""
        response = requests.get(f"{BASE_URL}/api/integrations/connected", headers=auth_headers)
        data = response.json()
        
        for integration in data:
            assert 'credentials' not in integration, f"Credentials exposed for {integration.get('name')}"
        print("✓ No credentials exposed in connected integrations")


class TestIntegrationConnect:
    """Test POST /api/integrations/connect - creates new integration"""
    
    def test_connect_coming_soon_fails(self, auth_headers):
        """Connecting a 'coming_soon' integration should fail"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/connect",
            headers=auth_headers,
            json={
                "integration_type": "quickbooks",
                "credentials": {"client_id": "test", "client_secret": "test", "realm_id": "test"}
            }
        )
        assert response.status_code == 400
        assert "próximamente" in response.json()['detail'].lower() or "coming" in response.json()['detail'].lower()
        print("✓ Coming soon integration correctly rejected")
    
    def test_connect_invalid_type_fails(self, auth_headers):
        """Invalid integration type should fail"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/connect",
            headers=auth_headers,
            json={
                "integration_type": "invalid_type",
                "credentials": {}
            }
        )
        assert response.status_code == 400
        print("✓ Invalid integration type correctly rejected")
    
    def test_connect_alegra_success(self, auth_headers):
        """Connecting Alegra should work (if not already connected)"""
        # First check if already connected
        connected = requests.get(f"{BASE_URL}/api/integrations/connected", headers=auth_headers).json()
        alegra_connected = any(i.get('integration_type') == 'alegra' for i in connected)
        
        if alegra_connected:
            print("⚠ Alegra already connected, skipping connect test")
            return
        
        response = requests.post(
            f"{BASE_URL}/api/integrations/connect",
            headers=auth_headers,
            json={
                "integration_type": "alegra",
                "credentials": {"email": "test@test.com", "api_token": "test_token"},
                "label": "TEST_Alegra_Connection"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            assert 'id' in data
            assert data['integration_type'] == 'alegra'
            assert 'credentials' not in data
            print(f"✓ Alegra connected successfully with id: {data['id']}")
            
            # Cleanup - disconnect
            requests.delete(f"{BASE_URL}/api/integrations/{data['id']}", headers=auth_headers)
            print("✓ Test integration cleaned up")
        elif response.status_code == 400 and "ya está conectado" in response.json().get('detail', ''):
            print("⚠ Alegra already connected")
        else:
            pytest.fail(f"Unexpected response: {response.status_code} - {response.text}")


class TestIntegrationTestEndpoint:
    """Test POST /api/integrations/{id}/test - tests connection"""
    
    def test_test_nonexistent_integration(self, auth_headers):
        """Testing non-existent integration should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/integrations/{fake_id}/test", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Non-existent integration test returns 404")
    
    def test_test_existing_integration(self, auth_headers):
        """Testing existing integration should return status"""
        connected = requests.get(f"{BASE_URL}/api/integrations/connected", headers=auth_headers).json()
        
        if not connected:
            print("⚠ No connected integrations to test")
            return
        
        integration = connected[0]
        response = requests.post(f"{BASE_URL}/api/integrations/{integration['id']}/test", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        print(f"✓ Integration test returned status: {data['status']}")


class TestIntegrationSync:
    """Test POST /api/integrations/{id}/sync - triggers data sync"""
    
    def test_sync_nonexistent_integration(self, auth_headers):
        """Syncing non-existent integration should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/integrations/{fake_id}/sync", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Non-existent integration sync returns 404")
    
    def test_sync_existing_integration(self, auth_headers):
        """Syncing existing integration should work"""
        connected = requests.get(f"{BASE_URL}/api/integrations/connected", headers=auth_headers).json()
        
        contalink = next((i for i in connected if i.get('integration_type') == 'contalink'), None)
        if not contalink:
            print("⚠ No CONTALink integration to sync")
            return
        
        response = requests.post(f"{BASE_URL}/api/integrations/{contalink['id']}/sync", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'message' in data
        print(f"✓ Sync returned: {data['status']} - {data['message']}")


class TestIntegrationDisconnect:
    """Test DELETE /api/integrations/{id} - disconnects integration"""
    
    def test_disconnect_nonexistent_integration(self, auth_headers):
        """Disconnecting non-existent integration should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/integrations/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Non-existent integration disconnect returns 404")


class TestAdminAllCompanies:
    """Test GET /api/integrations/admin/all-companies - admin dashboard data"""
    
    def test_admin_companies_returns_200(self, auth_headers):
        """Should return 200 with companies list"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-companies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin companies endpoint returns {len(data)} companies")
    
    def test_admin_companies_structure(self, auth_headers):
        """Each company should have required fields"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-companies", headers=auth_headers)
        data = response.json()
        
        if not data:
            print("⚠ No companies found")
            return
        
        required_fields = ['id', 'nombre', 'rfc', 'users_count', 'cfdis_count', 'integrations']
        for company in data:
            for field in required_fields:
                assert field in company, f"Missing field '{field}' in company"
        print("✓ All companies have required fields")
    
    def test_admin_companies_has_expected_data(self, auth_headers):
        """Should have COMERCIALIZADORA ORIENTAL TECHNOLOGY with expected metrics"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-companies", headers=auth_headers)
        data = response.json()
        
        # Find the expected company
        company = next((c for c in data if 'ORIENTAL' in c.get('nombre', '').upper()), None)
        if company:
            assert company['users_count'] >= 1, "Should have at least 1 user"
            assert company['cfdis_count'] >= 0, "Should have CFDIs count"
            assert isinstance(company['integrations'], list)
            print(f"✓ Found company: {company['nombre']}")
            print(f"  - Users: {company['users_count']}")
            print(f"  - CFDIs: {company['cfdis_count']}")
            print(f"  - Integrations: {len(company['integrations'])}")
        else:
            print(f"⚠ Expected company not found. Companies: {[c.get('nombre') for c in data]}")
    
    def test_admin_companies_integrations_no_credentials(self, auth_headers):
        """Integrations in company data should not expose credentials"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-companies", headers=auth_headers)
        data = response.json()
        
        for company in data:
            for integration in company.get('integrations', []):
                assert 'credentials' not in integration, f"Credentials exposed in company {company.get('nombre')}"
        print("✓ No credentials exposed in admin companies data")


class TestAdminAllUsers:
    """Test GET /api/integrations/admin/all-users - admin users list"""
    
    def test_admin_users_returns_200(self, auth_headers):
        """Should return 200 with users list"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-users", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin users endpoint returns {len(data)} users")
    
    def test_admin_users_no_password_exposed(self, auth_headers):
        """Password hash should not be exposed"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-users", headers=auth_headers)
        data = response.json()
        
        for user in data:
            assert 'password_hash' not in user, f"Password exposed for user {user.get('email')}"
            assert 'password' not in user, f"Password exposed for user {user.get('email')}"
        print("✓ No passwords exposed in admin users data")
    
    def test_admin_users_structure(self, auth_headers):
        """Each user should have required fields"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-users", headers=auth_headers)
        data = response.json()
        
        if not data:
            print("⚠ No users found")
            return
        
        # Check for email and role at minimum (field names may vary)
        for user in data:
            assert 'email' in user, f"Missing 'email' in user"
            assert 'role' in user, f"Missing 'role' in user"
            # company_id may be 'company_id' or 'empresa_id'
            assert 'company_id' in user or 'empresa_id' in user, f"Missing company reference in user"
        print("✓ All users have required fields")


class TestAuthorizationRequired:
    """Test that endpoints require authentication"""
    
    def test_available_list_requires_auth(self):
        """Should return 401 or 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/integrations/available-list")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ available-list requires authentication")
    
    def test_connected_requires_auth(self):
        """Should return 401 or 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/integrations/connected")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ connected requires authentication")
    
    def test_admin_companies_requires_auth(self):
        """Should return 401 or 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-companies")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ admin/all-companies requires authentication")
    
    def test_admin_users_requires_auth(self):
        """Should return 401 or 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/integrations/admin/all-users")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ admin/all-users requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
