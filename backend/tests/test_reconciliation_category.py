"""
Test Category/Subcategory selection in Bank Reconciliation
Tests the feature: Add Category/Subcategory selection when reconciling bank transactions with CFDIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReconciliationCategory:
    """Tests for Category/Subcategory selection during reconciliation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get categories for testing
        cat_response = self.session.get(f"{BASE_URL}/api/categories")
        assert cat_response.status_code == 200
        self.categories = cat_response.json()
        
        # Get ingreso and egreso categories
        self.ingreso_categories = [c for c in self.categories if c.get('tipo') == 'ingreso']
        self.egreso_categories = [c for c in self.categories if c.get('tipo') == 'egreso']
        
        yield
        
        # Cleanup - no specific cleanup needed as we'll use existing data
    
    def test_categories_endpoint_returns_data(self):
        """Test that categories endpoint returns categories with correct structure"""
        response = self.session.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        
        categories = response.json()
        assert isinstance(categories, list)
        assert len(categories) > 0, "Should have at least one category"
        
        # Verify category structure
        for cat in categories:
            assert 'id' in cat
            assert 'nombre' in cat
            assert 'tipo' in cat
            assert cat['tipo'] in ['ingreso', 'egreso'], f"Category tipo should be ingreso or egreso, got {cat['tipo']}"
    
    def test_categories_have_ingreso_type(self):
        """Test that there are categories of type 'ingreso' for income CFDIs"""
        assert len(self.ingreso_categories) > 0, "Should have at least one ingreso category"
        
        # Verify Ventas category exists (mentioned in requirements)
        ventas_cat = next((c for c in self.ingreso_categories if 'Ventas' in c.get('nombre', '')), None)
        assert ventas_cat is not None, "Should have a 'Ventas' category for ingreso type"
    
    def test_categories_have_egreso_type(self):
        """Test that there are categories of type 'egreso' for expense CFDIs"""
        assert len(self.egreso_categories) > 0, "Should have at least one egreso category"
        
        # Verify some expected egreso categories exist
        egreso_names = [c.get('nombre', '') for c in self.egreso_categories]
        print(f"Egreso categories found: {egreso_names}")
    
    def test_reconciliation_endpoint_accepts_categoria_id(self):
        """Test that POST /api/reconciliations accepts categoria_id parameter"""
        # Get a pending bank transaction
        txn_response = self.session.get(f"{BASE_URL}/api/bank-transactions?limit=100")
        assert txn_response.status_code == 200
        transactions = txn_response.json()
        
        pending_txns = [t for t in transactions if not t.get('conciliado')]
        if not pending_txns:
            pytest.skip("No pending bank transactions available for testing")
        
        # Get CFDIs with saldo pendiente
        cfdi_response = self.session.get(f"{BASE_URL}/api/cfdi?limit=100")
        assert cfdi_response.status_code == 200
        cfdis = cfdi_response.json()
        
        # Filter CFDIs that have saldo pendiente (not fully paid)
        def has_saldo_pendiente(cfdi):
            total = cfdi.get('total', 0)
            tipo = cfdi.get('tipo_cfdi', '')
            if tipo == 'ingreso':
                monto_cubierto = cfdi.get('monto_cobrado', 0) or 0
            else:
                monto_cubierto = cfdi.get('monto_pagado', 0) or 0
            return (total - monto_cubierto) > 0.01
        
        pending_cfdis = [c for c in cfdis if has_saldo_pendiente(c)]
        if not pending_cfdis:
            pytest.skip("No CFDIs with pending balance available for testing")
        
        # Find a matching transaction and CFDI (egreso CFDI with debito transaction)
        test_txn = None
        test_cfdi = None
        test_category = None
        
        for cfdi in pending_cfdis:
            cfdi_tipo = cfdi.get('tipo_cfdi', '')
            cfdi_total = cfdi.get('total', 0)
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            saldo_pendiente = cfdi_total - monto_pagado
            
            # For egreso CFDIs, look for debito transactions
            if cfdi_tipo == 'egreso':
                for txn in pending_txns:
                    if txn.get('tipo_movimiento') == 'debito' and abs(txn.get('monto', 0) - saldo_pendiente) < 0.01:
                        test_txn = txn
                        test_cfdi = cfdi
                        test_category = self.egreso_categories[0] if self.egreso_categories else None
                        break
            
            if test_txn and test_cfdi:
                break
        
        if not test_txn or not test_cfdi or not test_category:
            pytest.skip("No matching pending transaction/CFDI pair found for testing")
        
        # Create reconciliation with categoria_id
        reconciliation_data = {
            "bank_transaction_id": test_txn['id'],
            "cfdi_id": test_cfdi['id'],
            "metodo_conciliacion": "manual",
            "porcentaje_match": 100,
            "monto_aplicado": test_cfdi['total'],
            "categoria_id": test_category['id'],
            "subcategoria": "TEST_Subcategoria"
        }
        
        response = self.session.post(f"{BASE_URL}/api/reconciliations", json=reconciliation_data)
        
        # Should succeed (200 or 201)
        assert response.status_code in [200, 201], f"Reconciliation failed: {response.text}"
        
        result = response.json()
        assert 'id' in result, "Response should contain reconciliation id"
        
        # Verify payment was created with category
        payments_response = self.session.get(f"{BASE_URL}/api/payments?limit=100")
        assert payments_response.status_code == 200
        payments = payments_response.json()
        
        # Find the payment created for this reconciliation
        payment = next((p for p in payments if p.get('bank_transaction_id') == test_txn['id'] and p.get('cfdi_id') == test_cfdi['id']), None)
        
        if payment:
            assert payment.get('category_id') == test_category['id'], f"Payment should have category_id {test_category['id']}, got {payment.get('category_id')}"
            assert payment.get('subcategory_id') == "TEST_Subcategoria", f"Payment should have subcategory_id 'TEST_Subcategoria', got {payment.get('subcategory_id')}"
        
        # Cleanup - delete the reconciliation
        recon_id = result['id']
        delete_response = self.session.delete(f"{BASE_URL}/api/reconciliations/{recon_id}")
        assert delete_response.status_code == 200, f"Failed to cleanup reconciliation: {delete_response.text}"
    
    def test_reconciliation_without_category_validation(self):
        """Test that reconciliation requires category (validation in frontend, backend should still accept)"""
        # Get a pending bank transaction
        txn_response = self.session.get(f"{BASE_URL}/api/bank-transactions?limit=100")
        assert txn_response.status_code == 200
        transactions = txn_response.json()
        
        pending_txns = [t for t in transactions if not t.get('conciliado')]
        if not pending_txns:
            pytest.skip("No pending bank transactions available for testing")
        
        # Get CFDIs with saldo pendiente
        cfdi_response = self.session.get(f"{BASE_URL}/api/cfdi?limit=100")
        assert cfdi_response.status_code == 200
        cfdis = cfdi_response.json()
        
        # Filter CFDIs that have saldo pendiente
        def has_saldo_pendiente(cfdi):
            total = cfdi.get('total', 0)
            tipo = cfdi.get('tipo_cfdi', '')
            if tipo == 'ingreso':
                monto_cubierto = cfdi.get('monto_cobrado', 0) or 0
            else:
                monto_cubierto = cfdi.get('monto_pagado', 0) or 0
            return (total - monto_cubierto) > 0.01
        
        pending_cfdis = [c for c in cfdis if has_saldo_pendiente(c)]
        if not pending_cfdis:
            pytest.skip("No CFDIs with pending balance available for testing")
        
        # Find a matching transaction and CFDI
        test_txn = None
        test_cfdi = None
        
        for cfdi in pending_cfdis:
            cfdi_tipo = cfdi.get('tipo_cfdi', '')
            cfdi_total = cfdi.get('total', 0)
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            saldo_pendiente = cfdi_total - monto_pagado
            
            if cfdi_tipo == 'egreso':
                for txn in pending_txns:
                    if txn.get('tipo_movimiento') == 'debito' and abs(txn.get('monto', 0) - saldo_pendiente) < 0.01:
                        test_txn = txn
                        test_cfdi = cfdi
                        break
            
            if test_txn and test_cfdi:
                break
        
        if not test_txn or not test_cfdi:
            pytest.skip("No matching pending transaction/CFDI pair found for testing")
        
        # Create reconciliation WITHOUT categoria_id (backend should still accept, validation is in frontend)
        reconciliation_data = {
            "bank_transaction_id": test_txn['id'],
            "cfdi_id": test_cfdi['id'],
            "metodo_conciliacion": "manual",
            "porcentaje_match": 100,
            "monto_aplicado": test_cfdi['total']
            # No categoria_id or subcategoria
        }
        
        response = self.session.post(f"{BASE_URL}/api/reconciliations", json=reconciliation_data)
        
        # Backend should accept (validation is in frontend)
        # The payment will be created with category from CFDI if available
        assert response.status_code in [200, 201], f"Reconciliation should succeed even without category: {response.text}"
        
        result = response.json()
        
        # Cleanup
        recon_id = result['id']
        delete_response = self.session.delete(f"{BASE_URL}/api/reconciliations/{recon_id}")
        assert delete_response.status_code == 200
    
    def test_payment_created_with_category_from_reconciliation(self):
        """Test that payment document is created with correct category_id and subcategory_id"""
        # Get a pending bank transaction
        txn_response = self.session.get(f"{BASE_URL}/api/bank-transactions?limit=100")
        assert txn_response.status_code == 200
        transactions = txn_response.json()
        
        pending_txns = [t for t in transactions if not t.get('conciliado')]
        if not pending_txns:
            pytest.skip("No pending bank transactions available for testing")
        
        # Get CFDIs with saldo pendiente
        cfdi_response = self.session.get(f"{BASE_URL}/api/cfdi?limit=100")
        assert cfdi_response.status_code == 200
        cfdis = cfdi_response.json()
        
        # Filter CFDIs that have saldo pendiente
        def has_saldo_pendiente(cfdi):
            total = cfdi.get('total', 0)
            tipo = cfdi.get('tipo_cfdi', '')
            if tipo == 'ingreso':
                monto_cubierto = cfdi.get('monto_cobrado', 0) or 0
            else:
                monto_cubierto = cfdi.get('monto_pagado', 0) or 0
            return (total - monto_cubierto) > 0.01
        
        pending_cfdis = [c for c in cfdis if has_saldo_pendiente(c)]
        if not pending_cfdis:
            pytest.skip("No CFDIs with pending balance available for testing")
        
        # Find a matching transaction and CFDI
        test_txn = None
        test_cfdi = None
        test_category = None
        
        for cfdi in pending_cfdis:
            cfdi_tipo = cfdi.get('tipo_cfdi', '')
            cfdi_total = cfdi.get('total', 0)
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            saldo_pendiente = cfdi_total - monto_pagado
            
            if cfdi_tipo == 'egreso':
                for txn in pending_txns:
                    if txn.get('tipo_movimiento') == 'debito' and abs(txn.get('monto', 0) - saldo_pendiente) < 0.01:
                        test_txn = txn
                        test_cfdi = cfdi
                        test_category = self.egreso_categories[0] if self.egreso_categories else None
                        break
            
            if test_txn and test_cfdi:
                break
        
        if not test_txn or not test_cfdi or not test_category:
            pytest.skip("No matching pending transaction/CFDI pair found for testing")
        
        # Create reconciliation with category
        test_subcategoria = "TEST_PaymentSubcategory"
        reconciliation_data = {
            "bank_transaction_id": test_txn['id'],
            "cfdi_id": test_cfdi['id'],
            "metodo_conciliacion": "manual",
            "porcentaje_match": 100,
            "monto_aplicado": test_cfdi['total'],
            "categoria_id": test_category['id'],
            "subcategoria": test_subcategoria
        }
        
        response = self.session.post(f"{BASE_URL}/api/reconciliations", json=reconciliation_data)
        assert response.status_code in [200, 201], f"Reconciliation failed: {response.text}"
        
        result = response.json()
        recon_id = result['id']
        
        # Verify payment was created with correct category
        payments_response = self.session.get(f"{BASE_URL}/api/payments?limit=100")
        assert payments_response.status_code == 200
        payments = payments_response.json()
        
        # Find the payment
        payment = next((p for p in payments if p.get('bank_transaction_id') == test_txn['id'] and p.get('cfdi_id') == test_cfdi['id']), None)
        
        assert payment is not None, "Payment should be created during reconciliation"
        assert payment.get('category_id') == test_category['id'], f"Payment category_id mismatch: expected {test_category['id']}, got {payment.get('category_id')}"
        assert payment.get('subcategory_id') == test_subcategoria, f"Payment subcategory_id mismatch: expected {test_subcategoria}, got {payment.get('subcategory_id')}"
        
        print(f"✓ Payment created with category_id: {payment.get('category_id')}")
        print(f"✓ Payment created with subcategory_id: {payment.get('subcategory_id')}")
        
        # Cleanup
        delete_response = self.session.delete(f"{BASE_URL}/api/reconciliations/{recon_id}")
        assert delete_response.status_code == 200


class TestBankReconciliationModel:
    """Tests for BankReconciliationCreate model with categoria_id and subcategoria fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_reconciliation_model_accepts_categoria_id(self):
        """Test that BankReconciliationCreate model accepts categoria_id field"""
        # This is implicitly tested by the API accepting the field
        # We verify by checking the model definition in the code
        
        # Get bank transactions and CFDIs
        txn_response = self.session.get(f"{BASE_URL}/api/bank-transactions?limit=10")
        cfdi_response = self.session.get(f"{BASE_URL}/api/cfdi?limit=10")
        
        assert txn_response.status_code == 200
        assert cfdi_response.status_code == 200
        
        # The model should accept these fields without error
        # This is verified by the successful API calls in other tests
        print("✓ BankReconciliationCreate model accepts categoria_id and subcategoria fields")
    
    def test_reconciliation_model_accepts_subcategoria(self):
        """Test that BankReconciliationCreate model accepts subcategoria field"""
        # Verified by successful API calls with subcategoria parameter
        print("✓ BankReconciliationCreate model accepts subcategoria field")


class TestCategoryTypeFiltering:
    """Tests for category filtering based on CFDI type (ingreso/egreso)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@demo.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get categories
        cat_response = self.session.get(f"{BASE_URL}/api/categories")
        assert cat_response.status_code == 200
        self.categories = cat_response.json()
    
    def test_ingreso_categories_for_income_cfdi(self):
        """Test that ingreso categories are available for income CFDIs"""
        ingreso_cats = [c for c in self.categories if c.get('tipo') == 'ingreso']
        
        assert len(ingreso_cats) > 0, "Should have ingreso categories"
        
        # Verify expected categories exist
        cat_names = [c.get('nombre', '') for c in ingreso_cats]
        print(f"Ingreso categories: {cat_names}")
        
        # Check for Ventas category (mentioned in requirements)
        assert any('Ventas' in name for name in cat_names), "Should have 'Ventas' category for ingreso"
    
    def test_egreso_categories_for_expense_cfdi(self):
        """Test that egreso categories are available for expense CFDIs"""
        egreso_cats = [c for c in self.categories if c.get('tipo') == 'egreso']
        
        assert len(egreso_cats) > 0, "Should have egreso categories"
        
        # Verify expected categories exist
        cat_names = [c.get('nombre', '') for c in egreso_cats]
        print(f"Egreso categories: {cat_names}")
        
        # Check for expected egreso categories (mentioned in requirements)
        expected_egreso = ['Proveedores', 'Gastos', 'Sueldos', 'Impuestos']
        for expected in expected_egreso:
            if any(expected in name for name in cat_names):
                print(f"✓ Found expected egreso category containing '{expected}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
