"""
TaxnFin Cashflow - Categories and DIOT Export Tests
Tests for categories CRUD, subcategories, CFDI categorization, reconciliation status, and DIOT export
"""
import pytest
import requests
import os
import uuid as uuid_lib
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://satflow-manager.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"Login successful - User: {data['user']['nombre']}")


class TestCategoriesCRUD:
    """Categories CRUD endpoint tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers with token and company ID"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_list_categories(self, auth_headers):
        """Test listing all categories"""
        response = requests.get(f"{BASE_URL}/api/categories", headers=auth_headers)
        
        assert response.status_code == 200, f"List categories failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Categories found: {len(data)}")
    
    def test_list_categories_filter_by_tipo(self, auth_headers):
        """Test listing categories filtered by type"""
        # Test ingreso filter
        response = requests.get(f"{BASE_URL}/api/categories?tipo=ingreso", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for cat in data:
            assert cat['tipo'] == 'ingreso', f"Expected ingreso, got {cat['tipo']}"
        print(f"Ingreso categories: {len(data)}")
        
        # Test egreso filter
        response = requests.get(f"{BASE_URL}/api/categories?tipo=egreso", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for cat in data:
            assert cat['tipo'] == 'egreso', f"Expected egreso, got {cat['tipo']}"
        print(f"Egreso categories: {len(data)}")
    
    def test_create_category(self, auth_headers):
        """Test creating a new category"""
        unique_name = f"TEST_Category_{uuid_lib.uuid4().hex[:8]}"
        payload = {
            "nombre": unique_name,
            "tipo": "egreso",
            "color": "#EF4444",
            "icono": "folder"
        }
        
        response = requests.post(f"{BASE_URL}/api/categories", headers=auth_headers, json=payload)
        
        assert response.status_code == 200, f"Create category failed: {response.text}"
        data = response.json()
        assert data['status'] == 'success'
        assert 'category_id' in data
        assert data['nombre'] == unique_name
        print(f"Category created: {data['category_id']}")
        
        # Cleanup - delete the category
        requests.delete(f"{BASE_URL}/api/categories/{data['category_id']}", headers=auth_headers)
    
    def test_create_and_update_category(self, auth_headers):
        """Test creating and updating a category"""
        # Create
        unique_name = f"TEST_UpdateCat_{uuid_lib.uuid4().hex[:8]}"
        payload = {
            "nombre": unique_name,
            "tipo": "ingreso",
            "color": "#22C55E",
            "icono": "briefcase"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/categories", headers=auth_headers, json=payload)
        assert create_response.status_code == 200
        category_id = create_response.json()['category_id']
        
        # Update
        updated_name = f"TEST_Updated_{uuid_lib.uuid4().hex[:8]}"
        update_payload = {
            "nombre": updated_name,
            "tipo": "ingreso",
            "color": "#0EA5E9",
            "icono": "star"
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/categories/{category_id}", 
            headers=auth_headers, 
            json=update_payload
        )
        
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        data = update_response.json()
        assert data['status'] == 'success'
        print(f"Category updated: {category_id}")
        
        # Verify update by listing
        list_response = requests.get(f"{BASE_URL}/api/categories", headers=auth_headers)
        categories = list_response.json()
        updated_cat = next((c for c in categories if c['id'] == category_id), None)
        assert updated_cat is not None
        assert updated_cat['nombre'] == updated_name
        assert updated_cat['color'] == "#0EA5E9"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/categories/{category_id}", headers=auth_headers)
    
    def test_delete_category(self, auth_headers):
        """Test deleting a category"""
        # Create a category to delete
        unique_name = f"TEST_DeleteCat_{uuid_lib.uuid4().hex[:8]}"
        payload = {
            "nombre": unique_name,
            "tipo": "egreso",
            "color": "#6B7280",
            "icono": "folder"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/categories", headers=auth_headers, json=payload)
        assert create_response.status_code == 200
        category_id = create_response.json()['category_id']
        
        # Delete
        delete_response = requests.delete(f"{BASE_URL}/api/categories/{category_id}", headers=auth_headers)
        
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        data = delete_response.json()
        assert data['status'] == 'success'
        print(f"Category deleted: {category_id}")
        
        # Verify deletion (should not appear in active list)
        list_response = requests.get(f"{BASE_URL}/api/categories", headers=auth_headers)
        categories = list_response.json()
        deleted_cat = next((c for c in categories if c['id'] == category_id), None)
        assert deleted_cat is None, "Category should not appear in active list after deletion"


class TestSubcategoriesCRUD:
    """Subcategories CRUD endpoint tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_create_subcategory(self, auth_headers):
        """Test creating a subcategory"""
        # First create a parent category
        cat_name = f"TEST_ParentCat_{uuid_lib.uuid4().hex[:8]}"
        cat_payload = {
            "nombre": cat_name,
            "tipo": "egreso",
            "color": "#F97316",
            "icono": "folder"
        }
        
        cat_response = requests.post(f"{BASE_URL}/api/categories", headers=auth_headers, json=cat_payload)
        assert cat_response.status_code == 200
        category_id = cat_response.json()['category_id']
        
        # Create subcategory
        subcat_name = f"TEST_Subcat_{uuid_lib.uuid4().hex[:8]}"
        subcat_payload = {
            "category_id": category_id,
            "nombre": subcat_name
        }
        
        subcat_response = requests.post(f"{BASE_URL}/api/subcategories", headers=auth_headers, json=subcat_payload)
        
        assert subcat_response.status_code == 200, f"Create subcategory failed: {subcat_response.text}"
        data = subcat_response.json()
        assert data['status'] == 'success'
        assert 'subcategory_id' in data
        assert data['nombre'] == subcat_name
        print(f"Subcategory created: {data['subcategory_id']}")
        
        # Verify subcategory appears in category listing
        list_response = requests.get(f"{BASE_URL}/api/categories", headers=auth_headers)
        categories = list_response.json()
        parent_cat = next((c for c in categories if c['id'] == category_id), None)
        assert parent_cat is not None
        assert 'subcategorias' in parent_cat
        assert len(parent_cat['subcategorias']) > 0
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/subcategories/{data['subcategory_id']}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/categories/{category_id}", headers=auth_headers)
    
    def test_delete_subcategory(self, auth_headers):
        """Test deleting a subcategory"""
        # Create parent category
        cat_name = f"TEST_ParentCat2_{uuid_lib.uuid4().hex[:8]}"
        cat_payload = {
            "nombre": cat_name,
            "tipo": "ingreso",
            "color": "#10B981",
            "icono": "briefcase"
        }
        
        cat_response = requests.post(f"{BASE_URL}/api/categories", headers=auth_headers, json=cat_payload)
        category_id = cat_response.json()['category_id']
        
        # Create subcategory
        subcat_name = f"TEST_SubcatDel_{uuid_lib.uuid4().hex[:8]}"
        subcat_payload = {
            "category_id": category_id,
            "nombre": subcat_name
        }
        
        subcat_response = requests.post(f"{BASE_URL}/api/subcategories", headers=auth_headers, json=subcat_payload)
        subcategory_id = subcat_response.json()['subcategory_id']
        
        # Delete subcategory
        delete_response = requests.delete(f"{BASE_URL}/api/subcategories/{subcategory_id}", headers=auth_headers)
        
        assert delete_response.status_code == 200, f"Delete subcategory failed: {delete_response.text}"
        data = delete_response.json()
        assert data['status'] == 'success'
        print(f"Subcategory deleted: {subcategory_id}")
        
        # Cleanup parent category
        requests.delete(f"{BASE_URL}/api/categories/{category_id}", headers=auth_headers)
    
    def test_create_subcategory_invalid_category(self, auth_headers):
        """Test creating subcategory with invalid category ID"""
        subcat_payload = {
            "category_id": "invalid-category-id-12345",
            "nombre": "Test Subcategory"
        }
        
        response = requests.post(f"{BASE_URL}/api/subcategories", headers=auth_headers, json=subcat_payload)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Invalid category ID correctly rejected")


class TestCFDICategorization:
    """CFDI categorization endpoint tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_list_cfdis(self, auth_headers):
        """Test listing CFDIs"""
        response = requests.get(f"{BASE_URL}/api/cfdi", headers=auth_headers)
        
        assert response.status_code == 200, f"List CFDIs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"CFDIs found: {len(data)}")
        return data
    
    def test_categorize_cfdi_endpoint_exists(self, auth_headers):
        """Test that categorize CFDI endpoint exists"""
        # Get a CFDI to test with
        cfdis_response = requests.get(f"{BASE_URL}/api/cfdi", headers=auth_headers)
        cfdis = cfdis_response.json()
        
        if len(cfdis) == 0:
            pytest.skip("No CFDIs available to test categorization")
        
        cfdi_id = cfdis[0]['id']
        
        # Test categorize endpoint (even without valid category)
        response = requests.put(
            f"{BASE_URL}/api/cfdi/{cfdi_id}/categorize",
            headers=auth_headers
        )
        
        # Should return 200 even without category_id (just updates with empty)
        assert response.status_code == 200, f"Categorize endpoint failed: {response.text}"
        print(f"Categorize endpoint working for CFDI: {cfdi_id}")


class TestCFDIReconciliationStatus:
    """CFDI reconciliation status endpoint tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_update_reconciliation_status(self, auth_headers):
        """Test updating CFDI reconciliation status"""
        # Get a CFDI to test with
        cfdis_response = requests.get(f"{BASE_URL}/api/cfdi", headers=auth_headers)
        cfdis = cfdis_response.json()
        
        if len(cfdis) == 0:
            pytest.skip("No CFDIs available to test reconciliation status")
        
        cfdi_id = cfdis[0]['id']
        
        # Test each status
        for status in ['pendiente', 'conciliado', 'no_conciliable']:
            response = requests.put(
                f"{BASE_URL}/api/cfdi/{cfdi_id}/reconciliation-status?status={status}",
                headers=auth_headers
            )
            
            assert response.status_code == 200, f"Update status to {status} failed: {response.text}"
            data = response.json()
            assert data['status'] == 'success'
            print(f"Reconciliation status updated to: {status}")
    
    def test_invalid_reconciliation_status(self, auth_headers):
        """Test updating with invalid reconciliation status"""
        cfdis_response = requests.get(f"{BASE_URL}/api/cfdi", headers=auth_headers)
        cfdis = cfdis_response.json()
        
        if len(cfdis) == 0:
            pytest.skip("No CFDIs available")
        
        cfdi_id = cfdis[0]['id']
        
        response = requests.put(
            f"{BASE_URL}/api/cfdi/{cfdi_id}/reconciliation-status?status=invalid_status",
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid status, got {response.status_code}"
        print("Invalid reconciliation status correctly rejected")


class TestDIOTExport:
    """DIOT export endpoint tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_export_diot_csv(self, auth_headers):
        """Test DIOT CSV export"""
        response = requests.get(f"{BASE_URL}/api/export/diot", headers=auth_headers)
        
        assert response.status_code == 200, f"DIOT export failed: {response.text}"
        
        # Check content type is CSV
        content_type = response.headers.get('content-type', '')
        assert 'text/csv' in content_type, f"Expected CSV content type, got {content_type}"
        
        # Check content disposition header
        content_disposition = response.headers.get('content-disposition', '')
        assert 'DIOT_export.csv' in content_disposition, f"Expected DIOT filename, got {content_disposition}"
        
        # Check CSV has content
        content = response.text
        assert len(content) > 0, "CSV content is empty"
        
        # Check CSV header row
        lines = content.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least header row"
        header = lines[0]
        assert 'RFC' in header or 'Tipo' in header, f"CSV header missing expected columns: {header}"
        
        print(f"DIOT CSV exported successfully - {len(lines)} lines")
    
    def test_export_diot_with_date_filter(self, auth_headers):
        """Test DIOT export with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/export/diot?fecha_desde=2024-01-01&fecha_hasta=2024-12-31",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"DIOT export with dates failed: {response.text}"
        print("DIOT export with date filter working")


class TestBankStatementTemplate:
    """Bank statement template download tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_download_bank_statement_template(self, auth_headers):
        """Test downloading bank statement Excel template"""
        response = requests.get(f"{BASE_URL}/api/bank-transactions/template", headers=auth_headers)
        
        assert response.status_code == 200, f"Template download failed: {response.text}"
        
        # Check content type is Excel
        content_type = response.headers.get('content-type', '')
        assert 'spreadsheet' in content_type or 'excel' in content_type.lower() or 'octet-stream' in content_type, \
            f"Expected Excel content type, got {content_type}"
        
        # Check content disposition header
        content_disposition = response.headers.get('content-disposition', '')
        assert 'plantilla_estado_cuenta.xlsx' in content_disposition, \
            f"Expected template filename, got {content_disposition}"
        
        # Check content is not empty
        assert len(response.content) > 0, "Template file is empty"
        
        print(f"Bank statement template downloaded - {len(response.content)} bytes")


class TestGlobalExceptionHandler:
    """Test global exception handler returns proper JSON"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "X-Company-ID": data['user']['company_id'],
                "Content-Type": "application/json"
            }
        pytest.skip("Authentication failed")
    
    def test_404_returns_json(self, auth_headers):
        """Test that 404 errors return JSON"""
        response = requests.get(f"{BASE_URL}/api/nonexistent-endpoint", headers=auth_headers)
        
        assert response.status_code == 404
        
        # Should return JSON, not HTML
        content_type = response.headers.get('content-type', '')
        assert 'application/json' in content_type, f"Expected JSON for 404, got {content_type}"
        
        data = response.json()
        assert 'detail' in data
        print(f"404 returns proper JSON: {data}")
    
    def test_invalid_category_returns_json(self, auth_headers):
        """Test that invalid category ID returns JSON error"""
        response = requests.delete(
            f"{BASE_URL}/api/categories/invalid-id-12345",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        
        content_type = response.headers.get('content-type', '')
        assert 'application/json' in content_type, f"Expected JSON for error, got {content_type}"
        
        data = response.json()
        assert 'detail' in data
        print(f"Invalid category returns proper JSON: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
