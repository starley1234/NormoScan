"""
Tests for NormoScan Web UI.
"""
import pytest
from fastapi.testclient import TestClient


def get_client():
    from backend.app.main import app
    return TestClient(app)


def get_auth_headers(client):
    """Get auth headers for admin user."""
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if resp.status_code != 200:
        # Try to register first
        client.post("/api/auth/register", json={"username": "admin", "password": "admin123", "role": "admin"})
        resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestWebUIPages:
    """Test web UI pages render correctly."""
    
    def test_login_page(self):
        c = get_client()
        r = c.get("/web/login")
        assert r.status_code == 200
        assert "НормоСкан" in r.text
        assert "login-form" in r.text
    
    def test_dashboard_requires_auth(self):
        c = get_client()
        r = c.get("/web/")
        # Should redirect to login
        assert r.status_code in (302, 401)
    
    def test_dashboard_with_auth(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/", headers=h)
        assert r.status_code == 200
        assert "Дашборд" in r.text
    
    def test_checks_page(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/checks", headers=h)
        assert r.status_code == 200
        assert "Проверки" in r.text
    
    def test_upload_page(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/upload", headers=h)
        assert r.status_code == 200
        assert "upload-zone" in r.text
    
    def test_gosts_page(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/gosts", headers=h)
        assert r.status_code == 200
        assert "ГОСТы" in r.text
    
    def test_gallery_page(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/gallery", headers=h)
        assert r.status_code == 200
        assert "Галерея" in r.text
    
    def test_analytics_page(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/analytics", headers=h)
        assert r.status_code == 200
        assert "Аналитика" in r.text
    
    def test_team_page(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/team", headers=h)
        assert r.status_code == 200
        assert "Команда" in r.text
    
    def test_admin_page_requires_admin(self):
        c = get_client()
        # Create viewer user
        import uuid
        uname = f"viewer_{uuid.uuid4().hex[:6]}"
        c.post("/api/auth/register", json={"username": uname, "password": "pass123", "role": "viewer"})
        resp = c.post("/api/auth/login", data={"username": uname, "password": "pass123"})
        token = resp.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        
        r = c.get("/web/admin", headers=h, follow_redirects=False)
        # Should redirect for non-admin
        assert r.status_code == 302
    
    def test_admin_page_as_admin(self):
        c = get_client()
        h = get_auth_headers(c)
        r = c.get("/web/admin", headers=h)
        assert r.status_code == 200
        assert "Админка" in r.text


class TestStaticFiles:
    """Test static files are served."""
    
    def test_css_served(self):
        c = get_client()
        r = c.get("/web/static/css/app.css")
        assert r.status_code == 200
        assert "background" in r.text
    
    def test_js_served(self):
        c = get_client()
        r = c.get("/web/static/js/app.js")
        assert r.status_code == 200
        assert "API" in r.text


class TestSecurityHeaders:
    """Test security-related responses."""
    
    def test_root_redirects_to_web(self):
        c = get_client()
        r = c.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/web/" in r.headers.get("location", "")
    
    def test_validation_error_format(self):
        c = get_client()
        h = get_auth_headers(c)
        # Send invalid data
        r = c.post("/api/admin/settings", headers=h, json={"image_width": 9999})
        assert r.status_code in (400, 422)
        # Should return JSON, not HTML
        assert "application/json" in r.headers.get("content-type", "")
