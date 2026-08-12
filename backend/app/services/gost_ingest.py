import glob
import hashlib
import logging
import os
import re
from typing import Any

from sqlalchemy.orm import Session

from ..models.gost import Gost
from .rag_text import text_rag

logger = logging.getLogger(__name__)

GOST_RE = re.compile(r"ГОСТ\s*\d+[\.\-]\d+(?:\-\d+)?", re.IGNORECASE)

def file_hash_and_mtime(path: str):
    h = hashlib.sha256()
    size = 0
    try:
        with open(path,"rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
                size+=len(chunk)
        mtime = os.path.getmtime(path)
        return h.hexdigest()[:16], mtime, size
    except:
        return None, None, None

def ingest_folder(folder: str, db: Session=None, force: bool=False) -> dict[str,Any]:
    if not os.path.isdir(folder):
        return {"error": f"Folder not found: {folder}"}
    pdfs = glob.glob(os.path.join(folder, "**", "*.pdf"), recursive=True)
    pdfs += glob.glob(os.path.join(folder, "**", "*.PDF"), recursive=True)
    txts = glob.glob(os.path.join(folder, "**", "*.txt"), recursive=True)
    all_files = pdfs + txts
    results=[]
    skipped=0
    indexed=0
    for f in all_files:
        try:
            fhash, mtime, fsize = file_hash_and_mtime(f)
            # Check dedupe via DB if exists and not force
            if db is not None and not force and fhash:
                existing = db.query(Gost).filter(Gost.file_hash==fhash).first()
                if existing and existing.file_mtime==mtime:
                    skipped+=1
                    results.append({"filepath": f, "status":"skipped", "reason":"unchanged", "designation": existing.designation})
                    continue
                # Also check by designation + mtime
                designation_guess = GOST_RE.search(os.path.basename(f))
                designation_guess = designation_guess.group(0) if designation_guess else os.path.splitext(os.path.basename(f))[0]
                by_desig = db.query(Gost).filter(Gost.designation==designation_guess).first()
                if by_desig and by_desig.file_hash==fhash and by_desig.file_mtime==mtime and not force:
                    skipped+=1
                    results.append({"filepath": f, "status":"skipped", "reason":"unchanged"})
                    continue
            res = text_rag.ingest_gost_file(f)
            res["file_hash"]=fhash
            indexed+=1
            results.append({**res, "status":"indexed"})
            if db is not None:
                existing = db.query(Gost).filter(Gost.designation==res["designation"]).first()
                # versioning: if file changed, mark old as obsolete? Simple: update
                # Detect version from designation (e.g., ГОСТ 2.104-2006 -> 2006)
                version = None
                m = re.search(r"-(\d{4})", res["designation"])
                if m:
                    version = m.group(1)
                if not existing:
                    g = Gost(designation=res["designation"], title=res["designation"], filepath=f, chunks_json=[], status="indexed",
                             file_hash=fhash, file_mtime=mtime, file_size=fsize, version=version)
                    db.add(g)
                else:
                    # if hash changed, update
                    existing.filepath=f
                    existing.status="indexed"
                    existing.file_hash=fhash
                    existing.file_mtime=mtime
                    existing.file_size=fsize
                    existing.version=version
                    # simple obsolete check: if designation contains older year, mark?
                    # For demo, not auto obsolete
                db.commit()
        except Exception as e:
            logger.warning(f"ingest failed {f}: {e}", exc_info=True)
            results.append({"filepath": f, "error": str(e), "status":"failed"})
    return {"folder": folder, "files_found": len(all_files), "processed": indexed, "skipped": skipped, "details": results, "indexed": indexed}

def search_gost(query: str, top_k: int=5) -> dict[str,Any]:
    return text_rag.ask(query, top_k=top_k)

def list_obsolete(db: Session):
    return db.query(Gost).filter(Gost.is_obsolete==True).all()

def mark_obsolete(db: Session, designation: str, superseded_by: str):
    g = db.query(Gost).filter(Gost.designation==designation).first()
    if g:
        g.is_obsolete=True
        g.superseded_by=superseded_by
        db.commit()
    return g
