import os, sys, tempfile, shutil
import pytest

# Ensure backend in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ["DATABASE_URL"] = "sqlite:///./test_normoscan.db"
os.environ["VECTOR_DB"] = "memory"
os.environ["VLM_QUANTIZATION"] = "mock"
os.environ["OCR_ENGINE"] = "mock"
os.environ["APP_ENV"] = "development"

# init DB before any test
def _init():
    try:
        from backend.app.db import init_db
        init_db()
        # seed admin
        from backend.app.db import SessionLocal
        from backend.app.routers.auth import seed_admin
        db = SessionLocal()
        try:
            seed_admin(db)
        finally:
            db.close()
    except Exception as e:
        print(f"conftest init_db failed: {e}")

_init()

@pytest.fixture(scope="session")
def db_url():
    return "sqlite:///./test_normoscan.db"

@pytest.fixture
def tmp_storage(tmp_path):
    os.environ["STORAGE_PATH"] = str(tmp_path / "storage")
    os.makedirs(str(tmp_path / "storage" / "gosts"), exist_ok=True)
    os.makedirs(str(tmp_path / "storage" / "gallery"), exist_ok=True)
    return tmp_path
