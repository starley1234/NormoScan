from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.user import User
from ..security import get_current_user
from ..config import settings
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])

class SettingsIn(BaseModel):
    vlm_model: Optional[str]=None
    vlm_quantization: Optional[str]=None
    vlm_engine: Optional[str]=None
    max_context_window: Optional[int]=None
    image_width: Optional[int]=None
    vram_limit_gb: Optional[int]=None
    empty_cache_after_page: Optional[bool]=None
    max_concurrent_vlm: Optional[int]=None
    ocr_engine: Optional[str]=None
    ocr_ensemble: Optional[bool]=None

@router.get("/settings")
def get_settings(user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    return {
        "vlm_model": settings.vlm_model,
        "vlm_quantization": settings.vlm_quantization,
        "vlm_engine": settings.vlm_engine,
        "max_context_window": settings.max_context_window,
        "image_width": settings.image_width,
        "vram_limit_gb": settings.vram_limit_gb,
        "empty_cache_after_page": settings.empty_cache_after_page,
        "max_concurrent_vlm": settings.max_concurrent_vlm,
        "vector_db": settings.vector_db,
        "ocr_engine": settings.ocr_engine,
        "ocr_ensemble": settings.ocr_ensemble,
        "koseven_enabled": settings.koseven_enabled,
        "enable_metrics": settings.enable_metrics,
    }

@router.post("/settings")
def update_settings(inp: SettingsIn, user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    data = inp.model_dump(exclude_none=True) if hasattr(inp, "model_dump") else inp.dict(exclude_none=True)
    for k,v in data.items():
        if k=="max_context_window" and v>32768:
            raise HTTPException(400, "max_context_window max 32768")
        if k=="image_width" and not (512 <= v <= 800):
            raise HTTPException(400, "image_width must be 512..800")
        if k=="vlm_engine" and v not in ("transformers","vllm","mock"):
            raise HTTPException(400, "vlm_engine must be transformers/vllm/mock")
        setattr(settings, k, v)
        # also hot-switch VLM if model changed
        if k in ("vlm_model","vlm_quantization","vlm_engine"):
            try:
                from ..services.vlm import vlm_service
                vlm_service.switch_model(settings.vlm_model, settings.vlm_quantization, settings.vlm_engine)
            except: pass
    return {"status":"updated","settings": data}

@router.post("/switch-model", summary="Быстрое переключение модели (16GB ↔ лёгкая)")
def switch_model(model: str, quantization: str="mock", engine: str="mock", user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..services.vlm import vlm_service
    # Validate context
    settings.vlm_model=model
    settings.vlm_quantization=quantization
    settings.vlm_engine=engine
    res = vlm_service.switch_model(model, quantization, engine)
    return {"status":"switched", **res}

@router.get("/queue")
def queue_info(user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Forbidden")
    try:
        from ..celery_app import celery_app
        insp = celery_app.control.inspect()
        active = insp.active() or {}
        scheduled = insp.scheduled() or {}
        reserved = insp.reserved() or {}
        return {"active": active, "scheduled": scheduled, "reserved": reserved}
    except Exception as e:
        return {"active": {}, "note": f"Celery not available: {e}", "fallback":"sync mode"}

@router.post("/queue/purge")
def purge_queue(user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    try:
        from ..celery_app import celery_app
        celery_app.control.purge()
        return {"status":"purged"}
    except Exception as e:
        return {"status":"no-op", "error": str(e)}

@router.get("/dead-letters")
def dead_letters(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..models.check import DeadLetter
    items = db.query(DeadLetter).order_by(DeadLetter.created_at.desc()).limit(20).all()
    return {"items": [{"id":d.id,"check_id":d.check_id,"filename":d.filename,"error":d.error,"retry_count":d.retry_count,"created_at":d.created_at} for d in items]}

@router.get("/metrics", summary="Метрики (Prometheus json)")
def metrics(user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Forbidden")
    from ..core.metrics import metrics
    return metrics.snapshot()

@router.get("/users")
def list_users(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    users=db.query(User).all()
    return {"users": [{"id":u.id,"username":u.username,"role":u.role,"is_active":u.is_active,"email":u.email} for u in users]}

@router.post("/users/{user_id}/role")
def change_role(user_id:int, role:str, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    target=db.query(User).filter(User.id==user_id).first()
    if not target:
        raise HTTPException(404,"Not found")
    if role not in ("admin","normocontroller","engineer","viewer"):
        raise HTTPException(400,"Invalid role")
    target.role=role
    db.commit()
    return {"status":"ok","user_id":user_id,"role":role}

# Metadata schemas CRUD
class SchemaIn(BaseModel):
    name: str
    title: Optional[str]=None
    schema_json: Dict[str,Any]
    make_active: bool=True

@router.get("/schemas", summary="Список схем метаданных")
def list_schemas(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Forbidden")
    from ..services.metadata import list_schemas
    items = list_schemas(db)
    return {"schemas": [{"id":s.id,"name":s.name,"title":s.title,"is_active":s.is_active,"created_at":s.created_at, "schema": s.schema_json} for s in items]}

@router.post("/schemas", summary="Создать/обновить схему")
def upsert_schema(inp: SchemaIn, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..services.metadata import create_or_update_schema
    # Validate JSON schema basics
    if "type" not in inp.schema_json or "properties" not in inp.schema_json:
        raise HTTPException(400, "Invalid JSON schema")
    s = create_or_update_schema(db, inp.name, inp.schema_json, title=inp.title, make_active=inp.make_active, created_by=user.id)
    return {"id": s.id, "name": s.name, "is_active": s.is_active}

@router.post("/schemas/{schema_id}/activate")
def activate_schema(schema_id:int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..models.app_settings import MetadataSchema
    s = db.query(MetadataSchema).filter(MetadataSchema.id==schema_id).first()
    if not s: raise HTTPException(404, "Not found")
    for other in db.query(MetadataSchema).all():
        other.is_active=False
    s.is_active=True
    db.commit()
    return {"status":"activated","id":schema_id}

# Retention & Backup
@router.post("/retention/run", summary="Запустить retention (удалить PDF старше N дней, оставить JSON)")
def run_retention(days: int=90, trash_days: int=30, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..services.retention import run_retention as do_retention
    res = do_retention(db, days=days, trash_days=trash_days)
    return res

@router.get("/trash", summary="Корзина (trashed checks)")
def list_trash(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Forbidden")
    from ..services.retention import list_trash
    items = list_trash(db)
    return {"items": [{"id":c.id,"filename":c.filename,"status":c.status,"created_at":c.created_at,"filepath":c.filepath} for c in items]}

@router.post("/trash/{check_id}/restore", summary="Восстановить из корзины")
def restore_trash(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..services.retention import restore_check
    c = restore_check(db, check_id)
    if not c:
        raise HTTPException(404, "Not found or not trashed")
    return {"status":"restored","id":c.id}

@router.post("/backup", summary="Бэкап в 1 клик (tar.gz)")
def backup(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    from ..services.retention import create_backup
    from fastapi.responses import FileResponse
    import os
    path = create_backup(db)
    if not os.path.exists(path):
        raise HTTPException(500, "Backup failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/gzip")
