import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.gost import Gost
from ..models.user import User
from ..security import get_current_user
from ..services.gost_ingest import ingest_folder, search_gost
from ..services.rag_text import text_rag

router = APIRouter(prefix="/api/gosts", tags=["gosts"])

@router.get("/")
def list_gosts(skip:int=0, limit:int=50, include_obsolete: bool=False, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    q = db.query(Gost).order_by(Gost.designation)
    if not include_obsolete:
        q = q.filter((Gost.is_obsolete==False) | (Gost.is_obsolete==None))
    total=q.count()
    items=q.offset(skip).limit(limit).all()
    return {"total": total, "items": [{"id":g.id,"designation":g.designation,"title":g.title,"status":g.status,"created_at":g.created_at,"filepath":g.filepath,"version":g.version,"file_hash":g.file_hash,"is_obsolete":g.is_obsolete,"superseded_by":g.superseded_by,"file_mtime":g.file_mtime} for g in items]}

@router.post("/ingest")
def ingest(inp: dict, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Only admin/normocontroller")
    path = inp.get("path") or settings.gosts_path
    force = inp.get("force", False)
    res = ingest_folder(path, db, force=force)
    return res

@router.post("/upload")
def upload_gost(file: UploadFile=File(...), designation: str=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Forbidden")
    dest = os.path.join(settings.gosts_path, file.filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    res = text_rag.ingest_gost_file(dest, designation=designation)
    # dedupe by hash
    import hashlib
    h=None
    try:
        with open(dest,"rb") as f:
            h=hashlib.sha256(f.read()).hexdigest()[:16]
    except: pass
    g = db.query(Gost).filter(Gost.designation==res["designation"]).first()
    if g:
        g.filepath=dest
        g.status="indexed"
        g.file_hash=h
        g.file_mtime=os.path.getmtime(dest)
    else:
        g = Gost(designation=res["designation"], title=res["designation"], filepath=dest, status="indexed", file_hash=h, file_mtime=os.path.getmtime(dest))
        db.add(g)
    db.commit()
    return {"status":"indexed","detail":res}

@router.post("/search")
def search(inp: dict, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    query = inp.get("query") or inp.get("q")
    if not query:
        raise HTTPException(400, "query required")
    top_k = inp.get("top_k",5)
    return search_gost(query, top_k=top_k)

@router.post("/ask")
def ask(inp: dict, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return search_gost(inp.get("query",""), top_k=inp.get("top_k",3))

@router.get("/autocomplete")
def autocomplete(q: str = Query(..., description="Префикс ГОСТа"), limit: int=5, user: User=Depends(get_current_user)):
    # Auth required, but open for viewer+
    from ..services.rag_text import text_rag
    return {"query": q, "suggestions": text_rag.autocomplete(q, limit=limit)}

@router.get("/diff")
def diff_gosts(old_id: int, new_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..services.diff import gost_diff_by_id
    res = gost_diff_by_id(db, old_id, new_id)
    if not res:
        raise HTTPException(404, "GOST not found")
    return res

@router.post("/{gost_id}/obsolete")
def set_obsolete(gost_id:int, superseded_by: str=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    g=db.query(Gost).filter(Gost.id==gost_id).first()
    if not g: raise HTTPException(404,"Not found")
    g.is_obsolete=True
    g.superseded_by=superseded_by
    db.commit()
    return {"id": gost_id, "is_obsolete": True, "superseded_by": superseded_by}

@router.get("/obsolete/list")
def list_obsolete(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    items = db.query(Gost).filter(Gost.is_obsolete==True).all()
    return {"items": [{"id":g.id,"designation":g.designation,"superseded_by":g.superseded_by} for g in items]}

@router.delete("/{gost_id}")
def delete_gost(gost_id:int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    g=db.query(Gost).filter(Gost.id==gost_id).first()
    if not g: raise HTTPException(404,"Not found")
    db.delete(g); db.commit()
    return {"deleted": gost_id}
