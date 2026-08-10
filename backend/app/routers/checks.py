import os, shutil, uuid, hashlib, json, time, asyncio
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..db import get_db
from ..models.check import Check, PageResult, Feedback
from ..models.user import User
from ..security import get_current_user, has_permission
from ..config import settings
from ..tasks import enqueue_check, process_check_sync
from ..services.analytics import export_knowledge_base, search_knowledge_base
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/checks", tags=["checks"])

def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]

@router.post("/upload", summary="Загрузка PDF на проверку")
def upload_check(file: UploadFile = File(...), priority: int=5, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF allowed")
    if not has_permission(user, "check:create"):
        raise HTTPException(403, "No permission")
    data = file.file.read()
    fhash = _hash_bytes(data)
    # Dedupe check within window
    window = datetime.utcnow() - timedelta(minutes=settings.dedupe_window_minutes)
    dup = db.query(Check).filter(Check.file_hash==fhash, Check.created_at>=window, Check.status=="done").first()
    if dup:
        return {"check_id": dup.id, "status": "dedupe", "filename": file.filename, "dedupe_from": dup.id, "message": "Найден недавний результат для такого же файла (дедупликация)"}
    uid = str(uuid.uuid4())[:8]
    fname = f"{uid}_{file.filename}"
    dest = os.path.join(settings.storage_path, "uploads", fname)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        out.write(data)
    check = Check(filename=file.filename, filepath=dest, status="queued", priority=priority, created_by=user.id, file_hash=fhash)
    db.add(check); db.commit(); db.refresh(check)
    try:
        enqueue_check(check.id, priority=priority)
    except Exception as e:
        process_check_sync(check.id)
    return {"check_id": check.id, "status": check.status, "filename": file.filename, "file_hash": fhash}

@router.get("/", summary="Список проверок (реестр)")
def list_checks(skip: int=0, limit: int=20, status: Optional[str]=None, q: Optional[str]=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    query = db.query(Check).order_by(Check.created_at.desc())
    if status: query = query.filter(Check.status==status)
    if q:
        query = query.filter(or_(Check.filename.ilike(f"%{q}%"), Check.summary.ilike(f"%{q}%")))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"total": total, "items": [{"id":c.id,"filename":c.filename,"status":c.status,"priority":c.priority,"pages_total":c.pages_total,"pages_done":c.pages_done,"created_at":c.created_at,"finished_at":c.finished_at,"created_by":c.created_by,"file_hash":c.file_hash} for c in items]}

@router.get("/{check_id}")
def get_check(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    pages = db.query(PageResult).filter(PageResult.check_id==check_id).order_by(PageResult.page_number).all()
    return {
        "id": c.id, "filename": c.filename, "status": c.status, "priority": c.priority,
        "pages_total": c.pages_total, "pages_done": c.pages_done, "file_hash": c.file_hash,
        "meta_json": c.meta_json, "errors_json": c.errors_json, "summary": c.summary,
        "consistency": c.consistency_json, "checklist": c.checklist_json,
        "pages": [{"page_number":p.page_number,"status":p.status,"ocr_text":p.ocr_text[:500] if p.ocr_text else None,"ocr_confidence":p.ocr_confidence,"errors":p.errors,"crops":p.crops,"text_hits":p.text_hits,"visual_hits":p.visual_hits} for p in pages]
    }

@router.get("/{check_id}/stream", summary="SSE прогресс проверки")
def stream_check(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    # Simple SSE polling implementation
    def gen():
        for _ in range(120):
            db2 = next(get_db())
            try:
                c = db2.query(Check).filter(Check.id==check_id).first()
                if not c:
                    yield f"data: {json.dumps({'error':'not found'})}\n\n"
                    break
                payload = json.dumps({"id":c.id,"status":c.status,"pages_done":c.pages_done,"pages_total":c.pages_total,"summary":c.summary}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if c.status in ("done","failed","dead_letter"):
                    break
            finally:
                db2.close()
            time.sleep(0.5)
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@router.get("/{check_id}/annotations", summary="Аннотации bbox для отображения на чертеже")
def annotations(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    pages = db.query(PageResult).filter(PageResult.check_id==check_id).all()
    annot = []
    for p in pages:
        for e in (p.errors or []):
            annot.append({"page": p.page_number, "bbox": e.get("bbox"), "code": e.get("code"), "msg": e.get("msg"), "severity": e.get("severity"), "suggested_fix": e.get("suggested_fix"), "id": e.get("id")})
        # also crops
    return {"check_id": check_id, "annotations": annot, "crops": {p.page_number: p.crops for p in pages}}

@router.post("/{check_id}/retry")
def retry_check(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    c.status="queued"
    c.retry_count=0
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
        "checklist": c.checklist_json,
        "created_at": c.created_at,
    }

@router.post("/feedback")
def feedback(inp: dict, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
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
    if vote=="dislike":
        retrain_dir = os.path.join(settings.storage_path, "retrain")
        os.makedirs(retrain_dir, exist_ok=True)
        with open(os.path.join(retrain_dir, "feedback.log"), "a") as f:
            f.write(f"{fb.created_at} check={fb.check_id} err={fb.error_id} vote=👎 comment={fb.comment}\n")
        # Also mark error for retraining promotion
        with open(os.path.join(retrain_dir, "retrain_queue.jsonl"), "a") as f:
            f.write(json.dumps({"check_id":fb.check_id,"error_id":fb.error_id,"comment":fb.comment,"created_at": str(fb.created_at)}, ensure_ascii=False)+"\n")
    return {"id": fb.id, "status":"ok"}

@router.get("/knowledge/search", summary="Поиск по базе знаний изделий")
def knowledge_search(q: str, top_k: int=10, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return {"query": q, "results": search_knowledge_base(db, q, top_k=top_k)}

@router.get("/knowledge/export")
def knowledge_export(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Requires normocontroller")
    return export_knowledge_base(db)

@router.get("/meta/schema")
def meta_schema(db: Session=Depends(get_db)):
    from ..services.metadata import get_active_schema
    return get_active_schema(db)

class AskIn(BaseModel):
    query: str

@router.post("/{check_id}/ask")
def ask_document(check_id: int, inp: AskIn, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..mcp_server import tool_ask_document
    return tool_ask_document({"check_id": check_id, "query": inp.query})

@router.post("/{check_id}/suggest-fix", summary="Сгенерировать подсказку по исправлению для ошибки")
def suggest_fix(check_id: int, error_id: str, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = db.query(Check).filter(Check.id==check_id).first()
    if not c: raise HTTPException(404, "Not found")
    for e in (c.errors_json or []):
        if e.get("id")==error_id:
            from ..services.vlm import suggest_fix_for_error
            fix = e.get("suggested_fix") or suggest_fix_for_error(e)
            return {"error_id": error_id, "fix": fix, "confidence": e.get("fix_confidence",0.85)}
    raise HTTPException(404, "error_id not found")
