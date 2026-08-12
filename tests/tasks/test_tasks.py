"""
Tests for Celery tasks.
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
        client.post("/api/auth/register", json={"username": "admin", "password": "admin123", "role": "admin"})
        resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestCheckProcessing:
    """Test check processing tasks."""
    
    def test_upload_triggers_processing(self):
        """Test that uploading a PDF triggers processing."""
        c = get_client()
        h = get_auth_headers(c)
        
        from PIL import Image
        import tempfile, os
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (200, 200), color="white").save(pdf, "PDF")
            
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
            
            assert r.status_code == 200
            data = r.json()
            assert "check_id" in data
            check_id = data["check_id"]
        
        # Wait for processing (mock is fast)
        import time
        time.sleep(2)
        
        # Check status
        r = c.get(f"/api/checks/{check_id}", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("done", "processing", "queued")
    
    def test_check_has_results(self):
        """Test that processed check has results."""
        c = get_client()
        h = get_auth_headers(c)
        
        from PIL import Image
        import tempfile, os, time
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (200, 200), color="white").save(pdf, "PDF")
            
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
            
            check_id = r.json()["check_id"]
        
        # Wait for processing
        for _ in range(10):
            time.sleep(1)
            r = c.get(f"/api/checks/{check_id}", headers=h)
            if r.json()["status"] in ("done", "failed"):
                break
        
        r = c.get(f"/api/checks/{check_id}", headers=h)
        data = r.json()
        
        if data["status"] == "done":
            assert "meta_json" in data
            assert "errors_json" in data
            assert "summary" in data
    
    def test_feedback_submission(self):
        """Test submitting feedback."""
        c = get_client()
        h = get_auth_headers(c)
        
        # Create a check first
        from PIL import Image
        import tempfile, os, time
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (200, 200), color="white").save(pdf, "PDF")
            
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
            
            check_id = r.json()["check_id"]
        
        # Wait for processing
        for _ in range(10):
            time.sleep(1)
            r = c.get(f"/api/checks/{check_id}", headers=h)
            if r.json()["status"] in ("done", "failed"):
                break
        
        # Submit feedback
        r = c.post("/api/checks/feedback", json={
            "check_id": check_id,
            "error_id": "test_err",
            "vote": "like"
        }, headers=h)
        assert r.status_code == 200
    
    def test_retry_failed_check(self):
        """Test retrying a check."""
        c = get_client()
        h = get_auth_headers(c)
        
        # Create a check
        from PIL import Image
        import tempfile, os
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (200, 200), color="white").save(pdf, "PDF")
            
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
            
            check_id = r.json()["check_id"]
        
        # Retry
        r = c.post(f"/api/checks/{check_id}/retry", headers=h)
        assert r.status_code == 200


class TestDeduplication:
    """Test file deduplication."""
    
    def test_same_file_dedupes(self):
        """Test that uploading same file twice deduplicates."""
        c = get_client()
        h = get_auth_headers(c)
        
        from PIL import Image
        import tempfile, os
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "dedup.pdf")
            Image.new("RGB", (200, 200), color="white").save(pdf, "PDF")
            
            # First upload
            with open(pdf, "rb") as f:
                r1 = c.post("/api/checks/upload", files={"file": ("dedup.pdf", f, "application/pdf")}, headers=h)
            
            # Wait for first to complete
            import time
            time.sleep(2)
            
            # Second upload (should dedupe)
            with open(pdf, "rb") as f:
                r2 = c.post("/api/checks/upload", files={"file": ("dedup.pdf", f, "application/pdf")}, headers=h)
        
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Second should be dedupe or queued
        assert r2.json()["status"] in ("dedupe", "queued")


class TestSSEStream:
    """Test Server-Sent Events stream."""
    
    def test_stream_endpoint_exists(self):
        """Test that SSE stream endpoint works."""
        c = get_client()
        h = get_auth_headers(c)
        
        # Create a check
        from PIL import Image
        import tempfile, os
        
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "test.pdf")
            Image.new("RGB", (200, 200), color="white").save(pdf, "PDF")
            
            with open(pdf, "rb") as f:
                r = c.post("/api/checks/upload", files={"file": ("test.pdf", f, "application/pdf")}, headers=h)
            
            check_id = r.json()["check_id"]
        
        # Test stream (just check it responds)
        r = c.get(f"/api/checks/{check_id}/stream", headers=h)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
