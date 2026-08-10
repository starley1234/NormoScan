from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.gost import Gost
from ..models.user import User
from ..security import get_current_user
from ..services.gost_ingest import ingest_folder, search_gost
from ..services.rag_text import text_rag
from ..config import settings
import os, shutil, uuid

router = APIRouter(prefix="/api/gosts", tags=["gosts"])

@router.get("/")
def list_gosts(skip:int=0, limit:int=50, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    q = db.query(Gost).order_by(Gost.designation)
    total=q.count()
    items=q.offset(skip).limit(limit).all()
    return {"total": total, "items": [{"id":g.id,"designation":g.designation,"title":g.title,"status":g.status,"created_at":g.created_at,"filepath":g.filepath} for g in items]}

@router.post("/ingest")
def ingest(inp: dict, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Only admin/normocontroller")
    path = inp.get("path") or settings.gosts_path
    res = ingest_folder(path, db)
    return res

@router.post("/upload")
def upload_gost(file: UploadFile=File(...), designation: str=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Forbidden")
    dest = os.path.join(settings.gosts_path, file.filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    # index
    res = text_rag.ingest_gost_file(dest, designation=designation)
    # db
    g = Gost(designation=res["designation"], title=res["designation"], filepath=dest, status="indexed")
    db.add(g); db.commit()
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

@router.delete("/{gost_id}")
def delete_gost(gost_id:int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    g=db.query(Gost).filter(Gost.id==gost_id).first()
    if not g: raise HTTPException(404,"Not found")
    db.delete(g); db.commit()
    return {"deleted": gost_id}
