import logging
import os
import shutil
import tarfile
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..models.check import Check

logger = logging.getLogger(__name__)

TRASH_DIR = os.path.join(settings.storage_path, "trash")

def run_retention(db: Session, days: int=90, trash_days: int=30) -> dict:
    """
    Удаляет PDF старше `days`, оставляя JSON метаданные. Перемещает в trash на `trash_days`.
    """
    os.makedirs(TRASH_DIR, exist_ok=True)
    cutoff = datetime.utcnow() - timedelta(days=days)
    trash_cutoff = datetime.utcnow() - timedelta(days=trash_days)
    checks = db.query(Check).filter(Check.created_at < cutoff, Check.status!="trashed").all()
    moved=0
    for c in checks:
        try:
            if c.filepath and os.path.exists(c.filepath):
                # move to trash
                fname = os.path.basename(c.filepath)
                dest = os.path.join(TRASH_DIR, f"{c.id}_{fname}")
                shutil.move(c.filepath, dest)
                c.filepath = dest
                c.status = "trashed"
                moved+=1
            else:
                c.status="trashed"
        except Exception as e:
            logger.warning(f"retention move failed {c.id}: {e}")
    db.commit()
    # cleanup trash older than trash_days (permanent delete)
    purged=0
    trashed = db.query(Check).filter(Check.status=="trashed").all()
    for c in trashed:
        if c.created_at < trash_cutoff - timedelta(days=days):  # actually after trashed, check finished_at?
            # permanent delete file if still exists
            try:
                if c.filepath and os.path.exists(c.filepath) and TRASH_DIR in c.filepath:
                    os.remove(c.filepath)
                    purged+=1
            except: pass
    # also cleanup orphan files in TRASH_DIR
    try:
        for fname in os.listdir(TRASH_DIR):
            fpath=os.path.join(TRASH_DIR, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < trash_cutoff.timestamp():
                os.remove(fpath)
                purged+=1
    except: pass
    return {"moved_to_trash": moved, "purged": purged, "cutoff": cutoff.isoformat()}

def list_trash(db: Session):
    return db.query(Check).filter(Check.status=="trashed").order_by(Check.created_at.desc()).limit(50).all()

def restore_check(db: Session, check_id: int):
    c = db.query(Check).filter(Check.id==check_id, Check.status=="trashed").first()
    if not c:
        return None
    # move back to uploads if file in trash
    if c.filepath and TRASH_DIR in c.filepath and os.path.exists(c.filepath):
        dest = os.path.join(settings.storage_path, "uploads", os.path.basename(c.filepath).split("_",1)[-1])
        try:
            shutil.move(c.filepath, dest)
            c.filepath=dest
        except: pass
    c.status="done"
    db.commit()
    return c

def create_backup(db: Session) -> str:
    """
    pg_dump (sqlite → copy) + qdrant snapshot (mock) → tar.gz
    """
    backup_dir = os.path.join(settings.storage_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmpdir = os.path.join(backup_dir, f"tmp_{ts}")
    os.makedirs(tmpdir, exist_ok=True)
    # DB
    db_path = settings.database_url.replace("sqlite:///", "")
    if os.path.exists(db_path):
        shutil.copy2(db_path, os.path.join(tmpdir, "normoscan.db"))
    else:
        # pg_dump fallback (if postgres)
        try:
            import subprocess
            subprocess.run(["pg_dump", settings.database_url, "-f", os.path.join(tmpdir, "dump.sql")], timeout=10)
        except Exception as e:
            logger.warning(f"pg_dump failed: {e}")
            # create info file
            open(os.path.join(tmpdir, "db_info.txt"),"w").write(f"DB: {settings.database_url}\n")
    # storage meta
    try:
        checks = db.query(Check).count()
        with open(os.path.join(tmpdir, "meta.json"),"w") as f:
            import json
            json.dump({"checks": checks, "ts": ts}, f, ensure_ascii=False, indent=2)
    except: pass
    # qdrant snapshot mock
    try:
        with open(os.path.join(tmpdir, "qdrant_snapshot.json"),"w") as f:
            f.write('{"mock": true}')
    except: pass
    # tar
    tar_path = os.path.join(backup_dir, f"normoscan_backup_{ts}.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(tmpdir, arcname=f"backup_{ts}")
    shutil.rmtree(tmpdir, ignore_errors=True)
    return tar_path
