"""
Tests for RBAC (Role-Based Access Control).
"""
import pytest
from fastapi.testclient import TestClient


def get_client():
    from backend.app.main import app
    return TestClient(app)


def create_user(client, username, password, role):
    """Helper to create a user and return auth headers."""
    client.post("/api/auth/register", json={"username": username, "password": password, "role": role})
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestRBACPermissions:
    """Test role-based access control."""
    
    def test_admin_can_access_admin_endpoints(self):
        c = get_client()
        h = create_user(c, "rbac_admin", "pass123", "admin")
        
        r = c.get("/api/admin/settings", headers=h)
        assert r.status_code == 200
    
    def test_viewer_cannot_access_admin(self):
        c = get_client()
        h = create_user(c, "rbac_viewer", "pass123", "viewer")
        
        r = c.get("/api/admin/settings", headers=h)
        assert r.status_code == 403
    
    def test_engineer_cannot_access_admin(self):
        c = get_client()
        h = create_user(c, "rbac_engineer", "pass123", "engineer")
        
        r = c.get("/api/admin/settings", headers=h)
        assert r.status_code == 403
    
    def test_normocontroller_cannot_access_admin_settings(self):
        """Only admin can access admin settings."""
        c = get_client()
        h = create_user(c, "rbac_norm", "pass123", "normocontroller")
        
        r = c.get("/api/admin/settings", headers=h)
        assert r.status_code == 403
    
    def test_normocontroller_can_access_metrics(self):
        """Normocontroller can access metrics."""
        c = get_client()
        h = create_user(c, "rbac_norm_metrics", "pass123", "normocontroller")
        
        r = c.get("/api/admin/metrics", headers=h)
        assert r.status_code == 200
    
    def test_viewer_cannot_upload(self):
        c = get_client()
        h = create_user(c, "rbac_viewer2", "pass123", "viewer")
        
        from PIL import Image
        import io, tempfile, os
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (100, 100), color="white").save(pdf, "PDF")
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
        assert r.status_code == 403
    
    def test_engineer_can_upload(self):
        c = get_client()
        h = create_user(c, "rbac_eng2", "pass123", "engineer")
        
        from PIL import Image
        import tempfile, os
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (100, 100), color="white").save(pdf, "PDF")
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
        assert r.status_code == 200
    
    def test_viewer_can_read_checks(self):
        c = get_client()
        h = create_user(c, "rbac_viewer3", "pass123", "viewer")
        
        r = c.get("/api/checks/", headers=h)
        assert r.status_code == 200
    
    def test_viewer_can_read_gosts(self):
        c = get_client()
        h = create_user(c, "rbac_viewer4", "pass123", "viewer")
        
        r = c.get("/api/gosts/", headers=h)
        assert r.status_code == 200
    
    def test_viewer_cannot_ingest_gosts(self):
        c = get_client()
        h = create_user(c, "rbac_viewer5", "pass123", "viewer")
        
        r = c.post("/api/gosts/ingest", json={"path": "/tmp"}, headers=h)
        assert r.status_code == 403
    
    def test_normocontroller_can_ingest_gosts(self):
        c = get_client()
        h = create_user(c, "rbac_norm2", "pass123", "normocontroller")
        
        r = c.post("/api/gosts/ingest", json={"path": "/tmp/nonexistent"}, headers=h)
        # 200 even if folder doesn't exist (returns error in body)
        assert r.status_code == 200
    
    def test_admin_can_change_roles(self):
        c = get_client()
        admin_h = create_user(c, "rbac_admin2", "pass123", "admin")
        
        # Create target user
        create_user(c, "rbac_target", "pass123", "viewer")
        
        # Get user id
        from backend.app.db import SessionLocal
        from backend.app.models.user import User
        db = SessionLocal()
        target = db.query(User).filter(User.username == "rbac_target").first()
        db.close()
        
        r = c.post(f"/api/admin/users/{target.id}/role?role=engineer", headers=admin_h)
        assert r.status_code == 200
    
    def test_non_admin_cannot_change_roles(self):
        c = get_client()
        h = create_user(c, "rbac_norm3", "pass123", "normocontroller")
        
        r = c.post("/api/admin/users/1/role?role=viewer", headers=h)
        assert r.status_code == 403


class TestSecuritySettings:
    """Test security-related settings."""
    
    def test_default_secret_key_is_generated(self):
        """Test that empty secret key gets generated."""
        from backend.app.config import Settings
        
        s = Settings(secret_key="")
        assert len(s.secret_key) > 0
    
    def test_change_me_secret_is_regenerated(self):
        """Test that 'change-me' secret gets regenerated."""
        from backend.app.config import Settings
        
        s = Settings(secret_key="change-me")
        assert s.secret_key != "change-me"
    
    def test_cors_origins_parsing(self):
        """Test CORS origins parsing."""
        from backend.app.config import Settings
        
        s = Settings(cors_origins="*")
        assert s.cors_origins == "*"
        
        s2 = Settings(cors_origins="https://a.com, https://b.com")
        assert "https://a.com" in s2.cors_origins


class TestPermissionMatrix:
    """Test permission matrix directly."""
    
    def test_admin_has_all_permissions(self):
        from backend.app.security import PERMISSIONS, has_permission
        from backend.app.models.user import User
        
        admin = User(username="test", role="admin", hashed_password="*", is_active=True)
        assert has_permission(admin, "any:permission")
        assert has_permission(admin, "check:create")
        assert has_permission(admin, "admin:settings")
    
    def test_viewer_limited_permissions(self):
        from backend.app.security import has_permission
        from backend.app.models.user import User
        
        viewer = User(username="test", role="viewer", hashed_password="*", is_active=True)
        assert has_permission(viewer, "check:read")
        assert has_permission(viewer, "gost:read")
        assert not has_permission(viewer, "check:create")
        assert not has_permission(viewer, "admin:settings")
    
    def test_engineer_permissions(self):
        from backend.app.security import has_permission
        from backend.app.models.user import User
        
        engineer = User(username="test", role="engineer", hashed_password="*", is_active=True)
        assert has_permission(engineer, "check:create")
        assert has_permission(engineer, "check:read")
        assert not has_permission(engineer, "gallery:write")
        assert not has_permission(engineer, "admin:settings")
    
    def test_normocontroller_permissions(self):
        from backend.app.security import has_permission
        from backend.app.models.user import User
        
        norm = User(username="test", role="normocontroller", hashed_password="*", is_active=True)
        assert has_permission(norm, "check:create")
        assert has_permission(norm, "gallery:write")
        assert has_permission(norm, "analytics:read")
        assert not has_permission(norm, "admin:settings")
