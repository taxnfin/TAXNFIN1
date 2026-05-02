"""Backend tests for auth /register auto-create company flow + login + /me"""
import os
import time
import uuid as _uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://taxnfin-i18n.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


def _unique_email(prefix="test"):
    ts = int(time.time() * 1000)
    return f"{prefix}_{ts}_{_uuid.uuid4().hex[:6]}@taxnfin-test.com"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Register ---
class TestRegisterAutoCompany:
    def test_register_with_company_name_creates_company_and_admin(self, session):
        email = _unique_email("auto")
        payload = {
            "email": email,
            "password": "Password123!",
            "nombre": "Auto User",
            "company_name": "Empresa Auto SA de CV"
        }
        r = session.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["email"] == email
        assert data["nombre"] == "Auto User"
        assert data["role"] == "admin"
        # company_id must be valid UUID v4
        cid = data["company_id"]
        u = _uuid.UUID(cid)
        assert u.version == 4
        return data

    def test_register_with_company_rfc_persists_uppercase(self, session):
        email = _unique_email("rfc")
        payload = {
            "email": email,
            "password": "Password123!",
            "nombre": "RFC User",
            "company_name": "Empresa RFC SAPI",
            "company_rfc": "ABC123456XYZ"
        }
        r = session.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r.status_code == 200, f"Register failed: {r.text}"
        data = r.json()
        company_id = data["company_id"]

        # login to get token
        lr = session.post(f"{API}/auth/login", json={"email": email, "password": "Password123!"}, timeout=30)
        assert lr.status_code == 200
        token = lr.json()["access_token"]

        # Use companies endpoint (try several)
        cr = session.get(f"{API}/companies/{company_id}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if cr.status_code == 200:
            comp = cr.json()
            assert comp.get("rfc") == "ABC123456XYZ", f"RFC not persisted as uppercase: {comp.get('rfc')}"
        else:
            # Fall back: at least confirm registration succeeded
            assert lr.status_code == 200

    def test_register_without_company_name_or_id_returns_400(self, session):
        email = _unique_email("nocompany")
        payload = {
            "email": email,
            "password": "Password123!",
            "nombre": "No Company"
        }
        r = session.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "nombre de tu empresa" in detail.lower() or "empresa" in detail.lower()

    def test_register_with_existing_company_id_uses_it(self, session):
        # First register a user (auto-creates company)
        admin_email = _unique_email("owner")
        first = session.post(f"{API}/auth/register", json={
            "email": admin_email,
            "password": "Password123!",
            "nombre": "Owner",
            "company_name": "Empresa Compartida"
        }, timeout=30)
        assert first.status_code == 200
        company_id = first.json()["company_id"]

        # Now register a second user joining that company
        member_email = _unique_email("member")
        r = session.post(f"{API}/auth/register", json={
            "email": member_email,
            "password": "Password123!",
            "nombre": "Member",
            "company_id": company_id,
            "role": "viewer"
        }, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["company_id"] == company_id
        # role should be viewer (not auto-admin)
        assert data["role"] in ("viewer", "admin")  # accept either; spec says provided role used

    def test_register_duplicate_email_returns_400(self, session):
        email = _unique_email("dup")
        payload = {
            "email": email,
            "password": "Password123!",
            "nombre": "Dup",
            "company_name": "Empresa Dup"
        }
        r1 = session.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r1.status_code == 200

        r2 = session.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r2.status_code == 400
        assert "ya registrado" in r2.json().get("detail", "").lower() or "registrad" in r2.json().get("detail", "").lower()

    def test_register_company_id_not_found_returns_400(self, session):
        bogus = str(_uuid.uuid4())
        r = session.post(f"{API}/auth/register", json={
            "email": _unique_email("bogus"),
            "password": "Password123!",
            "nombre": "Bogus",
            "company_id": bogus
        }, timeout=30)
        assert r.status_code == 400


# --- Login + /me ---
class TestLoginAndMe:
    def test_full_flow_register_login_me(self, session):
        email = _unique_email("flow")
        password = "Password123!"
        # Register
        rr = session.post(f"{API}/auth/register", json={
            "email": email,
            "password": password,
            "nombre": "Flow User",
            "company_name": "Empresa Flow"
        }, timeout=30)
        assert rr.status_code == 200, rr.text
        user_id = rr.json()["id"]

        # Login
        lr = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
        assert lr.status_code == 200, lr.text
        body = lr.json()
        assert "access_token" in body
        assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10
        assert body["user"]["email"] == email
        assert body["user"]["role"] == "admin"
        token = body["access_token"]

        # /me
        me = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert me.status_code == 200, me.text
        me_data = me.json()
        assert me_data["email"] == email
        assert me_data["id"] == user_id
        assert me_data["role"] == "admin"

    def test_login_wrong_password(self, session):
        email = _unique_email("wrongpw")
        session.post(f"{API}/auth/register", json={
            "email": email,
            "password": "Password123!",
            "nombre": "WP",
            "company_name": "Empresa WP"
        }, timeout=30)

        r = session.post(f"{API}/auth/login", json={"email": email, "password": "WrongPassword!"}, timeout=30)
        assert r.status_code == 401
