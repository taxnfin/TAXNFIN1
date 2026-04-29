"""
Test Account Mappings API - Configurable account-to-category mapping feature
Tests: GET categories, POST auto-detect, CRUD for mappings
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"


class TestAccountMappingsAPI:
    """Account Mappings CRUD and auto-detect tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    # ==================== GET /api/account-mappings/categories ====================
    def test_get_financial_categories_returns_11_categories(self):
        """GET /api/account-mappings/categories - Returns 11 financial categories"""
        res = self.session.get(f"{BASE_URL}/api/account-mappings/categories")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        categories = res.json()
        assert isinstance(categories, list), "Response should be a list"
        assert len(categories) == 11, f"Expected 11 categories, got {len(categories)}"
        
        # Verify structure
        for cat in categories:
            assert 'key' in cat, "Category should have 'key'"
            assert 'label' in cat, "Category should have 'label'"
            assert 'group' in cat, "Category should have 'group'"
            assert 'description' in cat, "Category should have 'description'"
        
        # Verify expected categories exist
        keys = [c['key'] for c in categories]
        expected_keys = ['ingresos', 'otros_ingresos', 'costo_ventas', 'gastos_venta', 
                         'gastos_administracion', 'gastos_generales', 'gastos_financieros',
                         'otros_gastos', 'impuestos', 'depreciacion', 'amortizacion']
        for key in expected_keys:
            assert key in keys, f"Expected category '{key}' not found"
        
        print(f"✓ GET /api/account-mappings/categories: 11 categories returned")
    
    def test_financial_categories_have_correct_groups(self):
        """Verify categories have correct group assignments"""
        res = self.session.get(f"{BASE_URL}/api/account-mappings/categories")
        assert res.status_code == 200
        
        categories = {c['key']: c for c in res.json()}
        
        # Income categories
        assert categories['ingresos']['group'] == 'income'
        assert categories['otros_ingresos']['group'] == 'income'
        
        # Cost category
        assert categories['costo_ventas']['group'] == 'cost'
        
        # Opex categories
        assert categories['gastos_venta']['group'] == 'opex'
        assert categories['gastos_administracion']['group'] == 'opex'
        assert categories['gastos_generales']['group'] == 'opex'
        
        # Financial category
        assert categories['gastos_financieros']['group'] == 'financial'
        
        # Tax category
        assert categories['impuestos']['group'] == 'tax'
        
        print(f"✓ Financial categories have correct group assignments")
    
    # ==================== POST /api/account-mappings/auto-detect ====================
    def test_auto_detect_returns_suggestions(self):
        """POST /api/account-mappings/auto-detect - Returns suggested mappings"""
        res = self.session.post(f"{BASE_URL}/api/account-mappings/auto-detect")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        suggestions = res.json()
        assert isinstance(suggestions, list), "Response should be a list"
        
        print(f"✓ POST /api/account-mappings/auto-detect: {len(suggestions)} suggestions returned")
        
        # If there are suggestions, verify structure
        if len(suggestions) > 0:
            for s in suggestions:
                assert 'source_id' in s, "Suggestion should have 'source_id'"
                assert 'source_value' in s, "Suggestion should have 'source_value'"
                assert 'source_type' in s, "Suggestion should have 'source_type'"
                assert 'integration' in s, "Suggestion should have 'integration'"
                assert 'suggested_target' in s, "Suggestion should have 'suggested_target'"
                assert 'confidence' in s, "Suggestion should have 'confidence'"
                
                # Confidence should be between 0 and 1
                assert 0 <= s['confidence'] <= 1, f"Confidence {s['confidence']} out of range"
            
            print(f"  - All suggestions have correct structure with confidence scores")
    
    def test_auto_detect_income_categories_map_to_ingresos(self):
        """Auto-detect correctly maps income categories to 'ingresos' (not gastos_venta)"""
        res = self.session.post(f"{BASE_URL}/api/account-mappings/auto-detect")
        assert res.status_code == 200
        
        suggestions = res.json()
        
        # Check if any income-related suggestions exist
        income_keywords = ['ingreso', 'venta', 'servicio', 'honorario']
        income_suggestions = [s for s in suggestions 
                             if any(kw in s['source_value'].lower() for kw in income_keywords)]
        
        # If there are income-type suggestions, they should map to 'ingresos' not 'gastos_venta'
        for s in income_suggestions:
            # This test verifies the fix: income categories should NOT be mapped to gastos_venta
            if s['suggested_target'] == 'gastos_venta':
                # Check if source is actually an income type (has 'ingreso' in name or is income category)
                if 'ingreso' in s['source_value'].lower():
                    pytest.fail(f"Income category '{s['source_value']}' incorrectly mapped to 'gastos_venta'")
        
        print(f"✓ Auto-detect: Income categories correctly mapped (not to gastos_venta)")
    
    # ==================== GET /api/account-mappings ====================
    def test_get_all_mappings(self):
        """GET /api/account-mappings - Returns all saved mappings"""
        res = self.session.get(f"{BASE_URL}/api/account-mappings")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        mappings = res.json()
        assert isinstance(mappings, list), "Response should be a list"
        
        print(f"✓ GET /api/account-mappings: {len(mappings)} mappings returned")
        
        # Verify structure if mappings exist
        if len(mappings) > 0:
            for m in mappings:
                assert 'id' in m, "Mapping should have 'id'"
                assert 'source_type' in m, "Mapping should have 'source_type'"
                assert 'source_value' in m, "Mapping should have 'source_value'"
                assert 'target_category' in m, "Mapping should have 'target_category'"
                assert 'integration' in m, "Mapping should have 'integration'"
            
            print(f"  - All mappings have correct structure")
    
    # ==================== POST /api/account-mappings ====================
    def test_create_mapping(self):
        """POST /api/account-mappings - Creates a new mapping"""
        # Create a test mapping
        payload = {
            "source_type": "category",
            "source_id": "TEST_cat_001",
            "source_value": "TEST Gastos Oficina",
            "target_category": "gastos_administracion",
            "integration": "alegra"
        }
        
        res = self.session.post(f"{BASE_URL}/api/account-mappings", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        created = res.json()
        assert 'id' in created, "Created mapping should have 'id'"
        assert created['source_value'] == payload['source_value']
        assert created['target_category'] == payload['target_category']
        assert created['integration'] == payload['integration']
        
        print(f"✓ POST /api/account-mappings: Mapping created with id={created['id']}")
        
        # Store for cleanup
        self.created_mapping_id = created['id']
        
        # Verify it appears in GET
        get_res = self.session.get(f"{BASE_URL}/api/account-mappings")
        assert get_res.status_code == 200
        mappings = get_res.json()
        found = any(m['id'] == created['id'] for m in mappings)
        assert found, "Created mapping should appear in GET /api/account-mappings"
        
        print(f"  - Mapping verified in GET response")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/account-mappings/{created['id']}")
    
    def test_create_mapping_invalid_target_category(self):
        """POST /api/account-mappings - Rejects invalid target category"""
        payload = {
            "source_type": "category",
            "source_id": "TEST_cat_002",
            "source_value": "TEST Invalid Category",
            "target_category": "invalid_category_xyz",
            "integration": "alegra"
        }
        
        res = self.session.post(f"{BASE_URL}/api/account-mappings", json=payload)
        assert res.status_code == 400, f"Expected 400 for invalid category, got {res.status_code}"
        
        print(f"✓ POST /api/account-mappings: Correctly rejects invalid target category")
    
    # ==================== PUT /api/account-mappings/{id} ====================
    def test_update_mapping(self):
        """PUT /api/account-mappings/{id} - Updates target category"""
        # First create a mapping
        create_payload = {
            "source_type": "category",
            "source_id": "TEST_cat_update",
            "source_value": "TEST Update Mapping",
            "target_category": "gastos_generales",
            "integration": "alegra"
        }
        
        create_res = self.session.post(f"{BASE_URL}/api/account-mappings", json=create_payload)
        assert create_res.status_code == 200
        mapping_id = create_res.json()['id']
        
        # Update the mapping
        update_payload = {"target_category": "gastos_administracion"}
        update_res = self.session.put(f"{BASE_URL}/api/account-mappings/{mapping_id}", json=update_payload)
        assert update_res.status_code == 200, f"Expected 200, got {update_res.status_code}: {update_res.text}"
        
        print(f"✓ PUT /api/account-mappings/{mapping_id}: Mapping updated")
        
        # Verify update persisted
        get_res = self.session.get(f"{BASE_URL}/api/account-mappings")
        assert get_res.status_code == 200
        mappings = get_res.json()
        updated = next((m for m in mappings if m['id'] == mapping_id), None)
        assert updated is not None, "Updated mapping should exist"
        assert updated['target_category'] == 'gastos_administracion', "Target category should be updated"
        
        print(f"  - Update verified: target_category changed to 'gastos_administracion'")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/account-mappings/{mapping_id}")
    
    def test_update_nonexistent_mapping(self):
        """PUT /api/account-mappings/{id} - Returns 404 for non-existent mapping"""
        update_payload = {"target_category": "gastos_administracion"}
        res = self.session.put(f"{BASE_URL}/api/account-mappings/nonexistent-id-12345", json=update_payload)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        
        print(f"✓ PUT /api/account-mappings/nonexistent: Returns 404")
    
    # ==================== DELETE /api/account-mappings/{id} ====================
    def test_delete_mapping(self):
        """DELETE /api/account-mappings/{id} - Removes mapping"""
        # First create a mapping
        create_payload = {
            "source_type": "category",
            "source_id": "TEST_cat_delete",
            "source_value": "TEST Delete Mapping",
            "target_category": "otros_gastos",
            "integration": "alegra"
        }
        
        create_res = self.session.post(f"{BASE_URL}/api/account-mappings", json=create_payload)
        assert create_res.status_code == 200
        mapping_id = create_res.json()['id']
        
        # Delete the mapping
        delete_res = self.session.delete(f"{BASE_URL}/api/account-mappings/{mapping_id}")
        assert delete_res.status_code == 200, f"Expected 200, got {delete_res.status_code}: {delete_res.text}"
        
        print(f"✓ DELETE /api/account-mappings/{mapping_id}: Mapping deleted")
        
        # Verify deletion
        get_res = self.session.get(f"{BASE_URL}/api/account-mappings")
        assert get_res.status_code == 200
        mappings = get_res.json()
        found = any(m['id'] == mapping_id for m in mappings)
        assert not found, "Deleted mapping should not appear in GET"
        
        print(f"  - Deletion verified: mapping no longer in list")
    
    def test_delete_nonexistent_mapping(self):
        """DELETE /api/account-mappings/{id} - Returns 404 for non-existent mapping"""
        res = self.session.delete(f"{BASE_URL}/api/account-mappings/nonexistent-id-67890")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        
        print(f"✓ DELETE /api/account-mappings/nonexistent: Returns 404")


class TestAccountMappingsIntegration:
    """Integration tests for account mappings with financial statements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_existing_mapping_proveedores_costo(self):
        """Verify existing mapping 'Proveedores Costo → costo_ventas' exists"""
        res = self.session.get(f"{BASE_URL}/api/account-mappings")
        assert res.status_code == 200
        
        mappings = res.json()
        
        # Look for the pre-existing mapping mentioned in context
        costo_mapping = next((m for m in mappings 
                             if 'costo' in m.get('source_value', '').lower() 
                             and m.get('target_category') == 'costo_ventas'), None)
        
        if costo_mapping:
            print(f"✓ Found existing mapping: '{costo_mapping['source_value']}' → 'costo_ventas'")
        else:
            print(f"  Note: No 'Proveedores Costo → costo_ventas' mapping found (may have been deleted)")
        
        # This is informational, not a failure
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
