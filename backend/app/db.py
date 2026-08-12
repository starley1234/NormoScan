from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

connect_args = {}
if settings.is_sqlite():
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _migrate_sqlite():
    # Add missing columns for sqlite without alembic (dev convenience)
    try:
        insp = inspect(engine)
        # checks.file_hash etc.
        def ensure_column(table, col, coltype):
            if table not in insp.get_table_names():
                return
            cols = [c["name"] for c in insp.get_columns(table)]
            if col not in cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                    print(f"[migrate] Added {table}.{col}")
        ensure_column("checks","file_hash","VARCHAR(64)")
        ensure_column("checks","retry_count","INTEGER DEFAULT 0")
        ensure_column("checks","checklist_json","TEXT")
        ensure_column("page_results","ocr_confidence","FLOAT")
        ensure_column("gosts","file_hash","VARCHAR(64)")
        ensure_column("gosts","file_mtime","FLOAT")
        ensure_column("gosts","file_size","INTEGER")
        ensure_column("gosts","version","VARCHAR(32)")
        ensure_column("gosts","valid_from","DATETIME")
        ensure_column("gosts","valid_to","DATETIME")
        ensure_column("gosts","is_obsolete","BOOLEAN DEFAULT 0")
        ensure_column("gosts","superseded_by","VARCHAR(64)")
    except Exception as e:
        print(f"[migrate] sqlite migrate failed: {e}")

def init_db():
    # import models to register
    from .models import app_settings, check, gallery, gost, team, user  # noqa
    Base.metadata.create_all(bind=engine)
    if settings.is_sqlite():
        _migrate_sqlite()
        # ensure again after migrate
        Base.metadata.create_all(bind=engine)
