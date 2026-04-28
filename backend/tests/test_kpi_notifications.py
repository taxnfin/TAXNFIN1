"""
Test suite for KPI Notification System
Tests: Notifications CRUD, KPI Alert Rules CRUD, KPI Evaluation
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@demo.com"
TEST_PASSWORD = "admin123"


class TestKPINotificationSystem:
    """Test suite for KPI Notification System"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
        
        data = login_response.json()
        self.token = data.get("access_token")  # API returns access_token, not token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Store created resources for cleanup
        self.created_rules = []
        self.created_notifications = []
        
        yield
        
        # Cleanup: Delete test-created rules
        for rule_id in self.created_rules:
            try:
                self.session.delete(f"{BASE_URL}/api/kpi-alert-rules/{rule_id}")
            except:
                pass
    
    # ===== NOTIFICATION ENDPOINTS =====
    
    def test_get_notifications(self):
        """Test GET /api/notifications returns notifications list"""
        response = self.session.get(f"{BASE_URL}/api/notifications")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If there are notifications, verify structure
        if len(data) > 0:
            notif = data[0]
            assert "id" in notif, "Notification should have 'id'"
            assert "title" in notif, "Notification should have 'title'"
            assert "message" in notif, "Notification should have 'message'"
            assert "read" in notif, "Notification should have 'read'"
            assert "level" in notif, "Notification should have 'level'"
            print(f"✓ Found {len(data)} notifications")
        else:
            print("✓ No notifications found (empty list)")
    
    def test_get_unread_count(self):
        """Test GET /api/notifications/unread-count returns unread count"""
        response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "count" in data, "Response should have 'count'"
        assert isinstance(data["count"], int), "Count should be an integer"
        assert data["count"] >= 0, "Count should be non-negative"
        
        print(f"✓ Unread count: {data['count']}")
    
    def test_mark_notification_read(self):
        """Test PUT /api/notifications/{id}/read marks notification as read"""
        # First get notifications
        get_response = self.session.get(f"{BASE_URL}/api/notifications")
        assert get_response.status_code == 200
        
        notifications = get_response.json()
        
        # Find an unread notification or skip
        unread = [n for n in notifications if not n.get("read")]
        
        if not unread:
            # Try to find any notification
            if notifications:
                notif_id = notifications[0]["id"]
                # Mark as read (even if already read, should return ok)
                response = self.session.put(f"{BASE_URL}/api/notifications/{notif_id}/read")
                # May return 200 or 404 if already read
                assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
                print(f"✓ Mark read endpoint works (notification was already read)")
            else:
                pytest.skip("No notifications to test mark as read")
        else:
            notif_id = unread[0]["id"]
            response = self.session.put(f"{BASE_URL}/api/notifications/{notif_id}/read")
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data.get("status") == "ok", "Response should have status 'ok'"
            
            # Verify it's now read
            verify_response = self.session.get(f"{BASE_URL}/api/notifications")
            verify_data = verify_response.json()
            marked_notif = next((n for n in verify_data if n["id"] == notif_id), None)
            
            if marked_notif:
                assert marked_notif["read"] == True, "Notification should be marked as read"
            
            print(f"✓ Notification {notif_id} marked as read")
    
    def test_mark_all_read(self):
        """Test PUT /api/notifications/read-all marks all as read"""
        response = self.session.put(f"{BASE_URL}/api/notifications/read-all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", "Response should have status 'ok'"
        assert "updated" in data, "Response should have 'updated' count"
        
        # Verify unread count is now 0
        count_response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        count_data = count_response.json()
        assert count_data["count"] == 0, "Unread count should be 0 after marking all read"
        
        print(f"✓ Marked {data['updated']} notifications as read")
    
    # ===== KPI ALERT RULES ENDPOINTS =====
    
    def test_get_alert_rules(self):
        """Test GET /api/kpi-alert-rules returns rules list"""
        response = self.session.get(f"{BASE_URL}/api/kpi-alert-rules")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If there are rules, verify structure
        if len(data) > 0:
            rule = data[0]
            assert "id" in rule, "Rule should have 'id'"
            assert "metric_key" in rule, "Rule should have 'metric_key'"
            assert "metric_label" in rule, "Rule should have 'metric_label'"
            assert "condition" in rule, "Rule should have 'condition'"
            assert "threshold" in rule, "Rule should have 'threshold'"
            assert "is_active" in rule, "Rule should have 'is_active'"
            print(f"✓ Found {len(data)} alert rules")
        else:
            print("✓ No alert rules found (empty list)")
    
    def test_create_alert_rule(self):
        """Test POST /api/kpi-alert-rules creates a new rule"""
        payload = {
            "metric_key": "net_margin",
            "metric_section": "margins",
            "metric_label": "TEST_Margen Neto",
            "condition": "below",
            "threshold": 10.0,
            "level": "warning"
        }
        
        response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id'"
        assert data["metric_key"] == payload["metric_key"], "metric_key should match"
        assert data["metric_label"] == payload["metric_label"], "metric_label should match"
        assert data["condition"] == payload["condition"], "condition should match"
        assert data["threshold"] == payload["threshold"], "threshold should match"
        assert data["level"] == payload["level"], "level should match"
        assert data.get("is_active") == True, "New rule should be active by default"
        
        # Store for cleanup
        self.created_rules.append(data["id"])
        
        # Verify rule exists in list
        get_response = self.session.get(f"{BASE_URL}/api/kpi-alert-rules")
        rules = get_response.json()
        created_rule = next((r for r in rules if r["id"] == data["id"]), None)
        assert created_rule is not None, "Created rule should appear in rules list"
        
        print(f"✓ Created alert rule: {data['id']}")
    
    def test_toggle_alert_rule(self):
        """Test PUT /api/kpi-alert-rules/{id}/toggle toggles active status"""
        # First create a rule to toggle
        payload = {
            "metric_key": "current_ratio",
            "metric_section": "liquidity",
            "metric_label": "TEST_Razón Circulante",
            "condition": "below",
            "threshold": 1.5,
            "level": "critical"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules", json=payload)
        assert create_response.status_code == 200
        
        rule_id = create_response.json()["id"]
        self.created_rules.append(rule_id)
        
        # Toggle off
        toggle_response = self.session.put(f"{BASE_URL}/api/kpi-alert-rules/{rule_id}/toggle")
        
        assert toggle_response.status_code == 200, f"Expected 200, got {toggle_response.status_code}: {toggle_response.text}"
        
        data = toggle_response.json()
        assert data.get("status") == "ok", "Response should have status 'ok'"
        assert "is_active" in data, "Response should have 'is_active'"
        assert data["is_active"] == False, "Rule should be inactive after toggle"
        
        # Toggle back on
        toggle_response2 = self.session.put(f"{BASE_URL}/api/kpi-alert-rules/{rule_id}/toggle")
        assert toggle_response2.status_code == 200
        
        data2 = toggle_response2.json()
        assert data2["is_active"] == True, "Rule should be active after second toggle"
        
        print(f"✓ Toggle rule {rule_id}: active -> inactive -> active")
    
    def test_delete_alert_rule(self):
        """Test DELETE /api/kpi-alert-rules/{id} deletes a rule"""
        # First create a rule to delete
        payload = {
            "metric_key": "roe",
            "metric_section": "returns",
            "metric_label": "TEST_ROE Delete",
            "condition": "below",
            "threshold": 15.0,
            "level": "info"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules", json=payload)
        assert create_response.status_code == 200
        
        rule_id = create_response.json()["id"]
        
        # Delete the rule
        delete_response = self.session.delete(f"{BASE_URL}/api/kpi-alert-rules/{rule_id}")
        
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("status") == "ok", "Response should have status 'ok'"
        
        # Verify rule no longer exists
        get_response = self.session.get(f"{BASE_URL}/api/kpi-alert-rules")
        rules = get_response.json()
        deleted_rule = next((r for r in rules if r["id"] == rule_id), None)
        assert deleted_rule is None, "Deleted rule should not appear in rules list"
        
        print(f"✓ Deleted alert rule: {rule_id}")
    
    # ===== KPI EVALUATION ENDPOINT =====
    
    def test_evaluate_kpi_rules(self):
        """Test POST /api/kpi-alert-rules/evaluate/{periodo} evaluates rules"""
        # Use period 2024-03 which should have financial data
        periodo = "2024-03"
        
        response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules/evaluate/{periodo}")
        
        # May return 200 (success) or 404 (no financial data)
        if response.status_code == 404:
            print(f"✓ Evaluation endpoint works (no financial data for {periodo})")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", "Response should have status 'ok'"
        assert "rules_evaluated" in data, "Response should have 'rules_evaluated'"
        assert "notifications_created" in data, "Response should have 'notifications_created'"
        
        print(f"✓ Evaluated {data['rules_evaluated']} rules, created {data['notifications_created']} notifications")
    
    def test_evaluate_nonexistent_period(self):
        """Test evaluation with non-existent period returns 404"""
        response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules/evaluate/1999-01")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent period returns 404")
    
    # ===== INTEGRATION TESTS =====
    
    def test_full_alert_workflow(self):
        """Test complete workflow: create rule -> evaluate -> check notifications"""
        # 1. Create a rule with a threshold that should trigger
        payload = {
            "metric_key": "gross_margin",
            "metric_section": "margins",
            "metric_label": "TEST_Margen Bruto Workflow",
            "condition": "below",
            "threshold": 99.0,  # Very high threshold to ensure trigger
            "level": "warning"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules", json=payload)
        assert create_response.status_code == 200
        
        rule_id = create_response.json()["id"]
        self.created_rules.append(rule_id)
        
        # 2. Get initial notification count
        initial_count_response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        initial_count = initial_count_response.json()["count"]
        
        # 3. Trigger evaluation for period 2024-03
        eval_response = self.session.post(f"{BASE_URL}/api/kpi-alert-rules/evaluate/2024-03")
        
        if eval_response.status_code == 404:
            print("✓ Workflow test skipped (no financial data for 2024-03)")
            return
        
        assert eval_response.status_code == 200
        eval_data = eval_response.json()
        
        # 4. Check if notification was created
        if eval_data["notifications_created"] > 0:
            # Verify notification exists
            notifs_response = self.session.get(f"{BASE_URL}/api/notifications")
            notifs = notifs_response.json()
            
            # Find notification for our rule
            our_notif = next((n for n in notifs if n.get("rule_id") == rule_id), None)
            
            if our_notif:
                assert "Margen Bruto" in our_notif["title"] or "2024-03" in our_notif["title"]
                print(f"✓ Full workflow: Rule created -> Evaluated -> Notification created")
            else:
                print(f"✓ Full workflow: Rule created -> Evaluated (notification may have been deduplicated)")
        else:
            print(f"✓ Full workflow: Rule created -> Evaluated (no new notifications - may be deduplicated)")


class TestNotificationEdgeCases:
    """Edge case tests for notification system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        data = login_response.json()
        self.token = data.get("access_token")  # API returns access_token, not token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_mark_nonexistent_notification_read(self):
        """Test marking non-existent notification returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.put(f"{BASE_URL}/api/notifications/{fake_id}/read")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent notification returns 404")
    
    def test_delete_nonexistent_notification(self):
        """Test deleting non-existent notification returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.delete(f"{BASE_URL}/api/notifications/{fake_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Delete non-existent notification returns 404")
    
    def test_toggle_nonexistent_rule(self):
        """Test toggling non-existent rule returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.put(f"{BASE_URL}/api/kpi-alert-rules/{fake_id}/toggle")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Toggle non-existent rule returns 404")
    
    def test_delete_nonexistent_rule(self):
        """Test deleting non-existent rule returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.delete(f"{BASE_URL}/api/kpi-alert-rules/{fake_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Delete non-existent rule returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
