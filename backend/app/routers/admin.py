from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.user import User
from ..security import get_current_user
from ..config import settings
from pydantic import BaseModel
from typing import Optional, Literal

router = APIRouter(prefix="/api/admin", tags=["admin"])

class SettingsIn(BaseModel):
    vlm_model: Optional[str]=None
    vlm_quantization: Optional[str]=None
    max_context_window: Optional[int]=None
    image_width: Optional[int]=None
    vram_limit_gb: Optional[int]=None
    empty_cache_after_page: Optional[bool]=None
    max_concurrent_vlm: Optional[int]=None

@router.get("/settings")
def get_settings(user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    return {
        "vlm_model": settings.vlm_model,
        "vlm_quantization": settings.vlm_quantization,
        "max_context_window": settings.max_context_window,
        "image_width": settings.image_width,
        "vram_limit_gb": settings.vram_limit_gb,
        "empty_cache_after_page": settings.empty_cache_after_page,
        "max_concurrent_vlm": settings.max_concurrent_vlm,
        "vector_db": settings.vector_db,
        "ocr_engine": settings.ocr_engine,
        "koseven_enabled": settings.koseven_enabled,
    }

@router.post("/settings")
def update_settings(inp: SettingsIn, user: User=Depends(get_current_user)):
    if user.role!="admin":
        raise HTTPException(403, "Only admin")
    # In real app, persist to DB or .env; here mutate runtime
    for k,v in inp.dict(exclude_none=True).items():
        setattr(settings, k, v)
        # also validate
        if k=="max_context_window" and v>32768:
            raise HTTPException(400, "max_context_window max 32768")
        if k=="image_width" and not (512 <= v <= 800):
            raise HTTPException(400, "image_width must be 512..800")
    return {"status":"updated","settings": inp.dict(exclude_none=True)}

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
