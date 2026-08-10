def test_koseven_role_map():
    from backend.app.core.koseven import map_koseven_role
    assert map_koseven_role("admin")=="admin"
    assert map_koseven_role("normocontrol")=="normocontroller"
    assert map_koseven_role("engineer")=="engineer"
    assert map_koseven_role("user")=="viewer"
    assert map_koseven_role("unknown")=="viewer"

def test_koseven_header_auth():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    c = TestClient(app)
    # Without KOSEVEN_ENABLED, header should be ignored but not crash
    r = c.get("/health")
    assert r.status_code==200
    # Test with header when enabled? For now just ensure endpoint works
    from backend.app.config import settings
    orig = settings.koseven_enabled
    settings.koseven_enabled = True
    try:
        # Mock: X-Koseven-Role header should create ephemeral user in security.get_current_user_optional
        # We test via security function directly
        from backend.app.security import has_permission
        from backend.app.models.user import User
        u = User(username="koseven_normocontrol", role="normocontroller", hashed_password="*", is_active=True)
        assert has_permission(u, "check:create")==True
        assert has_permission(u, "unknown:perm")==False
        admin = User(username="admin", role="admin", hashed_password="*", is_active=True)
        assert has_permission(admin, "any:thing")==True
    finally:
        settings.koseven_enabled = orig
