import os, shutil, uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.check import Check, PageResult, Feedback
from ..models.user import User
from ..security import get_current_user, has_permission
from ..config import settings
from ..tasks import enqueue_check, process_check_sync
from ..services.analytics import export_knowledge_base
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/checks", tags=["checks"])

@router.post("/upload", summary="Загрузка PDF на проверку")
def upload_check(file: UploadFile = File(...), priority: int=5, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF allowed")
    if not has_permission(user, "check:create"):
        raise HTTPException(403, "No permission")
    uid = str(uuid.uuid4())[:8]
    fname = f"{uid}_{file.filename}"
    dest = os.path.join(settings.storage_path, "uploads", fname)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    check = Check(filename=file.filename, filepath=dest, status="queued", priority=priority, created_by=user.id)
    db.add(check); db.commit(); db.refresh(check)
    # enqueue
    try:
        enqueue_check(check.id, priority=priority)
    except Exception as e:
        # fallback sync if no celery
        process_check_sync(check.id)
    return {"check_id": check.id, "status": check.status, "filename": file.filename}

@router.get("/", summary="Список проверок (реестр)")
def list_checks(skip: int=0, limit: int=20, status: Optional[str]=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    q = db.query(Check).order_by(Check.created_at.desc())
    if status: q = q.filter(Check.status==status)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"total": total, "items": [{"id":c.id,"filename":c.filename,"status":c.status,"priority":c.priority,"pages_total":c.pages_total,"pages_done":c.pages_done,"created_at":c.created_at,"finished_at":c.finished_at,"created_by":c.created_by} for c in items]}

@router.get("/{check_id}")
def get_check(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    pages = db.query(PageResult).filter(PageResult.check_id==check_id).order_by(PageResult.page_number).all()
    return {
        "id": c.id, "filename": c.filename, "status": c.status, "priority": c.priority,
        "pages_total": c.pages_total, "pages_done": c.pages_done,
        "meta_json": c.meta_json, "errors_json": c.errors_json, "summary": c.summary,
        "consistency": c.consistency_json,
        "pages": [{"page_number":p.page_number,"status":p.status,"ocr_text":p.ocr_text[:500] if p.ocr_text else None,"errors":p.errors,"crops":p.crops,"text_hits":p.text_hits,"visual_hits":p.visual_hits} for p in pages]
    }

@router.post("/{check_id}/retry")
def retry_check(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    c.status="queued"
    db.commit()
    enqueue_check(c.id, priority=c.priority)
    return {"status":"queued"}

@router.get("/{check_id}/report")
def report(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    return {
        "check_id": c.id,
        "filename": c.filename,
        "status": c.status,
        "metadata": c.meta_json,
        "errors": c.errors_json,
        "summary": c.summary,
        "consistency": c.consistency_json,
        "created_at": c.created_at,
    }

@router.post("/feedback")
def feedback(inp: dict, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    # inp: check_id, page_number, error_id, vote (like/dislike or 👍/👎), comment
    vote = inp.get("vote")
    if vote in ["👍","👎"]:
        vote = "like" if vote=="👍" else "dislike"
    fb = Feedback(
        check_id=inp["check_id"],
        page_number=inp.get("page_number"),
        error_id=inp.get("error_id"),
        vote=vote,
        comment=inp.get("comment"),
        created_by=user.id
    )
    db.add(fb); db.commit()
    # If dislike, mark for retraining folder
    if vote=="dislike":
        # copy to retraining folder
        retrain_dir = os.path.join(settings.storage_path, "retrain")
        os.makedirs(retrain_dir, exist_ok=True)
        # log
        with open(os.path.join(retrain_dir, "feedback.log"), "a") as f:
            f.write(f"{fb.created_at} check={fb.check_id} err={fb.error_id} vote=👎 comment={fb.comment}\n")
    return {"id": fb.id, "status":"ok"}

@router.get("/knowledge/export")
def knowledge_export(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    # only normocontroller/admin
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Requires normocontroller")
    return export_knowledge_base(db)

# Metadata template
@router.get("/meta/schema")
def meta_schema():
    from ..services.metadata import DEFAULT_SCHEMA
    return DEFAULT_SCHEMA

class AskIn(BaseModel):
    query: str

@router.post("/{check_id}/ask")
def ask_document(check_id: int, inp: AskIn, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..mcp_server import tool_ask_document
    return tool_ask_document({"check_id": check_id, "query": inp.query})
